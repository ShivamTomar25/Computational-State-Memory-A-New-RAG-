from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.memory_systems.common.registry.adapter import MemorySystemAdapter, source_preview
from app.memory_systems.common.schemas.canonical import IngestionResult
from app.memory_systems.common.schemas.memory import CapabilityStatus, MemoryContextItem
from app.memory_systems.common.token_budget.service import apply_token_budget, estimate_tokens
from app.memory_systems.csm.models import (
    CsmActivationItem,
    CsmActivationRun,
    CsmEvidence,
    CsmReviewRequest,
    CsmStateDependency,
    CsmStateEvidenceLink,
    CsmStateHistory,
    CsmStateVariable,
    CsmUpdateEvent,
)
from app.memory_systems.csm.v2_engine import (
    CSM_V2_IMPLEMENTATION_VERSION,
    build_state_value_payload,
    compact_evidence_context,
    compact_state_context,
    dependency_score_for_state,
    route_query,
    score_evidence,
    score_state,
    should_supersede,
    state_key_for_source_v2,
    state_status_for_source_v2,
    tokenize as csm_v2_tokenize,
    update_operator_for_source_v2,
    update_previous_supersession,
    update_reason_for_source_v2,
)


class CsmAdapter(MemorySystemAdapter):
    system_type = "csm"

    def capability_status(self) -> CapabilityStatus:
        return CapabilityStatus(
            ingestion="available",
            retrieval="available",
            conversation_memory="available",
            answer_generation="requires_llm",
            incremental_update="available",
            embeddings="available",
            provider="available",
        )

    def configuration(self) -> dict:
        return {
            "activation_top_k": settings.csm_activation_top_k,
            "activation_token_budget": settings.csm_activation_token_budget,
            "implementation_version": CSM_V2_IMPLEMENTATION_VERSION,
            "state_engine": "deterministic_structured_sources_v2",
            "query_router": "deterministic_feature_router_v2",
            "context_contract": "grounded_answer_context_blocks_v1",
        }

    def ingest_sources(self, db: Session, *, instance, sources: list) -> list[IngestionResult]:
        results: list[IngestionResult] = []

        for source in sources:
            evidence = self.upsert_evidence(db=db, instance=instance, source=source)

            if source.source_type == "conversation":
                review = self.upsert_review_request(
                    db=db,
                    instance=instance,
                    source=source,
                    evidence=evidence,
                )
                native_id = review.id
                native_type = "csm_review_request"
                status = "pending_review"
            else:
                state = self.upsert_state_from_evidence(
                    db=db,
                    instance=instance,
                    source=source,
                    evidence=evidence,
                )
                native_id = state.id
                native_type = "csm_state_variable"
                status = "state_updated" if source.source_type == "patient_information" else "candidate_state"

            results.append(
                IngestionResult(
                    native_record_type=native_type,
                    native_record_id=native_id,
                    canonical_source_id=source.id,
                    source_hash=source.content_hash,
                    status=status,
                )
            )

        return results

    def retrieve(self, db: Session, *, instance, query: str, top_k: int, token_budget: int, retrieval_mode):
        route = route_query(query)
        query_terms = csm_v2_tokenize(query)
        states = list(
            db.scalars(
                select(CsmStateVariable).where(
                    CsmStateVariable.system_instance_id == instance.id,
                    CsmStateVariable.status.in_(["active", "candidate"]),
                )
            ).all()
        )
        evidence_by_state = self.evidence_by_state(db=db, states=states)
        dependency_counts = self.dependency_counts(db=db, instance=instance)
        state_candidates = []

        for state in states:
            evidence = evidence_by_state.get(state.id)
            score, components, reason = score_state(
                query_terms=query_terms,
                route=route,
                state=state,
                evidence=evidence,
                dependency_score=dependency_score_for_state(state, dependency_counts),
            )
            content = compact_state_context(state=state, evidence=evidence, route=route, components=components)
            state_candidates.append(
                {
                    "kind": "state",
                    "state": state,
                    "evidence": evidence,
                    "score": score,
                    "components": components,
                    "reason": reason,
                    "content": content,
                    "token_count": estimate_tokens(content),
                }
            )

        evidence_candidates = []
        evidence_rows = list(
            db.scalars(
                select(CsmEvidence).where(
                    CsmEvidence.system_instance_id == instance.id,
                    CsmEvidence.is_active.is_(True),
                )
            ).all()
        )

        for evidence in evidence_rows:
            score, components, reason = score_evidence(query_terms=query_terms, route=route, evidence=evidence)
            content = compact_evidence_context(evidence=evidence, route=route, components=components)
            evidence_candidates.append(
                {
                    "kind": "evidence",
                    "state": None,
                    "evidence": evidence,
                    "score": score,
                    "components": components,
                    "reason": reason,
                    "content": content,
                    "token_count": estimate_tokens(content),
                }
            )

        scored = self.merge_activation_candidates(
            state_candidates=state_candidates,
            evidence_candidates=evidence_candidates,
            route_mode=route.mode,
        )
        run = CsmActivationRun(
            system_instance_id=instance.id,
            conversation_id=None,
            query_text=query,
            token_budget=token_budget,
            status="completed",
        )
        db.add(run)
        db.flush()
        db.add(
            CsmUpdateEvent(
                system_instance_id=instance.id,
                trigger_source_id=None,
                event_type="query_route",
                operator="deterministic_csm_v2_query_router",
                input_snapshot={"query": query, "retrieval_mode": retrieval_mode},
                output_snapshot={
                    "mode": route.mode,
                    "features": route.features,
                    "reason": route.reason,
                    "fallback_strategy": route.fallback_strategy,
                    "preferred_state_types": list(route.preferred_state_types),
                    "preferred_evidence_types": list(route.preferred_evidence_types),
                },
                status="completed",
            )
        )

        items: list[MemoryContextItem] = []

        candidate_limit = min(settings.csm_activation_top_k, max(top_k * 2, top_k))

        for index, candidate in enumerate(scored[:candidate_limit], start=1):
            state = candidate["state"]
            evidence = candidate["evidence"]
            selected = candidate["score"] >= 0.10

            if state is not None:
                components = candidate["components"]
                db.add(
                    CsmActivationItem(
                        activation_run_id=run.id,
                        state_variable_id=state.id,
                        rank=index,
                        relevance_score=components.get("relevance", candidate["score"]),
                        dependency_score=components.get("dependency", 0),
                        confidence_score=components.get("confidence", state.confidence),
                        utility_score=candidate["score"],
                        estimated_token_cost=candidate["token_count"],
                        selected=selected,
                        selection_reason=f"{candidate['reason']} route={route.mode}",
                    )
                )

            canonical_source_id = evidence.canonical_source_id if evidence is not None else None
            document_id = evidence.document_id if evidence is not None else None
            page_number = evidence.page_number if evidence is not None else None
            section_id = evidence.section_id if evidence is not None else None
            event_time = evidence.valid_time if evidence is not None else state.valid_from if state is not None else None
            native_type = "csm_state_variable" if state is not None else "csm_evidence"
            native_id = state.id if state is not None else evidence.id if evidence is not None else None
            source_type = "state" if state is not None else evidence.source_type if evidence is not None else "evidence"
            source_subtype = state.state_type if state is not None else evidence.observation_type if evidence is not None else None
            items.append(
                MemoryContextItem(
                    rank=index,
                    score=candidate["score"],
                    source_type=source_type,
                    source_subtype=source_subtype,
                    content_preview=source_preview(candidate["content"]),
                    content=candidate["content"],
                    canonical_source_id=canonical_source_id,
                    system_native_type=native_type,
                    system_native_id=native_id,
                    document_id=document_id,
                    page_number=page_number,
                    section_id=section_id,
                    conversation_id=evidence.conversation_id if evidence is not None else None,
                    message_id=evidence.message_id if evidence is not None else None,
                    event_time=event_time,
                    token_count=candidate["token_count"],
                    metadata={
                        "implementation_version": CSM_V2_IMPLEMENTATION_VERSION,
                        "route_mode": route.mode,
                        "route_reason": route.reason,
                        "route_features": route.features,
                        "fallback_strategy": route.fallback_strategy,
                        "state_key": state.state_key if state is not None else None,
                        "evidence_id": str(evidence.id) if evidence is not None else None,
                        "activation_components": candidate["components"],
                        "current_version": state.current_version if state is not None else None,
                    },
                )
            )

        db.flush()
        budget = apply_token_budget(items, token_budget=token_budget)

        warnings = [
            f"CSM v2 route={route.mode}; state/evidence context follows the standard grounded-answer contract."
        ]
        return budget.included[:top_k], warnings, "ready"

    def get_statistics(self, db: Session, *, instance) -> dict:
        evidence = db.scalar(
            select(func.count()).select_from(CsmEvidence).where(
                CsmEvidence.system_instance_id == instance.id,
                CsmEvidence.is_active.is_(True),
            )
        )
        states = db.scalar(
            select(func.count()).select_from(CsmStateVariable).where(
                CsmStateVariable.system_instance_id == instance.id
            )
        )
        activations = db.scalar(
            select(func.count()).select_from(CsmActivationRun).where(
                CsmActivationRun.system_instance_id == instance.id
            )
        )

        return {
            "evidence": int(evidence or 0),
            "state_variables": int(states or 0),
            "activation_runs": int(activations or 0),
            "document_extraction": "requires_llm",
            "conversation_claim_extraction": "candidate_only",
        }

    def upsert_evidence(self, *, db: Session, instance, source) -> CsmEvidence:
        evidence_type = evidence_type_for_source(source)
        evidence = db.scalar(
            select(CsmEvidence).where(
                CsmEvidence.system_instance_id == instance.id,
                CsmEvidence.canonical_source_id == source.id,
                CsmEvidence.evidence_type == evidence_type,
            )
        )
        verification_status = verification_status_for_source(source)

        if evidence is None:
            evidence = CsmEvidence(
                system_instance_id=instance.id,
                canonical_source_id=source.id,
                evidence_type=evidence_type,
                observation_type=source.source_subtype,
                content=source.content_text,
                structured_value={
                    **(source.structured_payload or {}),
                    "csm_implementation_version": CSM_V2_IMPLEMENTATION_VERSION,
                },
                normalized_value=normalized_state_value(source),
                unit=source.structured_payload.get("unit"),
                source_type=source.source_type,
                document_id=source.document_id,
                page_number=source.page_number,
                section_id=source.section_id,
                conversation_id=source.conversation_id,
                message_id=source.message_id,
                valid_time=source.valid_time,
                recorded_time=source.recorded_time,
                confidence=confidence_for_source(source),
                verification_status=verification_status,
                extraction_method="deterministic_structured_mapping"
                if source.source_type == "patient_information"
                else "document_span_candidate_extraction"
                if source.source_type == "document"
                else "conversation_proposal_extraction",
                extractor_version="2",
                is_active=True,
            )
            db.add(evidence)
            db.flush()
        else:
            evidence.content = source.content_text
            evidence.structured_value = {
                **(source.structured_payload or {}),
                "csm_implementation_version": CSM_V2_IMPLEMENTATION_VERSION,
            }
            evidence.extractor_version = "2"
            evidence.is_active = True

        return evidence

    def upsert_review_request(self, *, db: Session, instance, source, evidence: CsmEvidence) -> CsmReviewRequest:
        review = db.scalar(
            select(CsmReviewRequest).where(
                CsmReviewRequest.system_instance_id == instance.id,
                CsmReviewRequest.canonical_source_id == source.id,
                CsmReviewRequest.proposed_state_type == source.source_subtype,
            )
        )
        proposed_value = {
            "content": source.content_text,
            "structured": source.structured_payload,
            "evidence_id": str(evidence.id),
            "source_hash": source.content_hash,
        }

        if review is None:
            review = CsmReviewRequest(
                system_instance_id=instance.id,
                patient_id=source.patient_id,
                canonical_source_id=source.id,
                proposed_claim=source.content_text,
                proposed_state_type=source.source_subtype,
                proposed_value=proposed_value,
                support_status="insufficient_evidence",
                risk_level=risk_level_for_source(source),
                status="pending",
            )
            db.add(review)
            db.flush()
        elif review.status == "pending":
            review.proposed_claim = source.content_text
            review.proposed_value = proposed_value
            review.support_status = "insufficient_evidence"
            review.risk_level = risk_level_for_source(source)
            db.flush()

        return review

    def upsert_state_from_evidence(self, *, db: Session, instance, source, evidence: CsmEvidence) -> CsmStateVariable:
        state_type = source.source_subtype
        state_key = state_key_for_source_v2(source)
        now = datetime.now(timezone.utc)
        state = db.scalar(
            select(CsmStateVariable).where(
                CsmStateVariable.system_instance_id == instance.id,
                CsmStateVariable.state_type == state_type,
                CsmStateVariable.state_key == state_key,
            )
        )

        if state is not None and (state.current_value.get("lineage") or {}).get("source_hash") == source.content_hash:
            self.ensure_evidence_link(db=db, state=state, evidence=evidence)
            if "dependency_ids" not in (state.current_value or {}):
                self.apply_dependency_metadata(db=db, instance=instance, state=state, history=None)
            db.flush()
            return state

        operation = "supersede" if should_supersede(state.current_value if state is not None else None, source, evidence) else "upsert"
        current_version = 1 if state is None else state.current_version + 1
        previous_value = state.current_value if state is not None else None
        supersedes = list((previous_value or {}).get("evidence_ids") or []) if operation == "supersede" else []
        new_value = build_state_value_payload(
            source=source,
            evidence=evidence,
            operation=operation,
            version=current_version,
            previous_value=previous_value,
            supersedes=supersedes,
            dependency_ids=[],
        )

        update_event = CsmUpdateEvent(
            system_instance_id=instance.id,
            trigger_source_id=source.id,
            event_type="state_update",
            operator=update_operator_for_source_v2(source),
            input_snapshot={
                "canonical_source_id": str(source.id),
                "content_hash": source.content_hash,
                "previous_state_id": str(state.id) if state is not None else None,
            },
            output_snapshot={
                "state_key": state_key,
                "operation": operation,
                "schema_version": new_value["schema_version"],
                "supersedes": supersedes,
            },
            status="completed",
        )
        db.add(update_event)
        db.flush()

        if state is None:
            state = CsmStateVariable(
                system_instance_id=instance.id,
                state_type=state_type,
                state_key=state_key,
                current_value=new_value,
                confidence=evidence.confidence,
                uncertainty=new_value["uncertainty_components"],
                trend=None,
                prediction=None,
                status=state_status_for_source_v2(source),
                valid_from=source.valid_time,
                valid_to=None,
                current_version=1,
                update_operator=update_operator_for_source_v2(source),
                last_updated_at=now,
            )
            db.add(state)
            db.flush()
            history = CsmStateHistory(
                state_variable_id=state.id,
                version_number=state.current_version,
                previous_value=None,
                new_value=new_value,
                previous_confidence=None,
                new_confidence=state.confidence,
                update_reason=update_reason_for_source_v2(source, operation),
                valid_from=source.valid_time,
                valid_to=None,
                update_event_id=update_event.id,
            )
            db.add(history)
        else:
            previous_confidence = state.confidence
            history_previous_value = update_previous_supersession(previous_value, evidence_id=str(evidence.id))
            state.current_value = new_value
            state.confidence = max(0.0, min(1.0, (state.confidence * 0.35) + (evidence.confidence * 0.65)))
            state.current_version = current_version
            state.status = state_status_for_source_v2(source)
            state.uncertainty = new_value["uncertainty_components"]
            state.update_operator = update_operator_for_source_v2(source)
            state.last_updated_at = now
            db.flush()
            history = CsmStateHistory(
                state_variable_id=state.id,
                version_number=state.current_version,
                previous_value=history_previous_value,
                new_value=new_value,
                previous_confidence=previous_confidence,
                new_confidence=state.confidence,
                update_reason=update_reason_for_source_v2(source, operation),
                valid_from=source.valid_time,
                valid_to=None,
                update_event_id=update_event.id,
            )
            db.add(history)

        self.ensure_evidence_link(db=db, state=state, evidence=evidence)
        self.apply_dependency_metadata(db=db, instance=instance, state=state, history=history)
        db.flush()

        return state

    def ensure_evidence_link(self, *, db: Session, state: CsmStateVariable, evidence: CsmEvidence) -> None:
        link = db.get(CsmStateEvidenceLink, {"state_variable_id": state.id, "evidence_id": evidence.id})

        if link is None:
            db.add(
                CsmStateEvidenceLink(
                    state_variable_id=state.id,
                    evidence_id=evidence.id,
                    contribution_type=relation_for_evidence(evidence),
                    contribution_weight=1.0,
                )
            )

    def evidence_by_state(self, *, db: Session, states: list[CsmStateVariable]) -> dict:
        if not states:
            return {}

        state_ids = [state.id for state in states]
        rows = list(
            db.execute(
                select(CsmStateEvidenceLink, CsmEvidence)
                .join(CsmEvidence, CsmStateEvidenceLink.evidence_id == CsmEvidence.id)
                .where(CsmStateEvidenceLink.state_variable_id.in_(state_ids))
            ).all()
        )
        grouped = {}

        for link, evidence in rows:
            current = grouped.get(link.state_variable_id)
            if current is None or evidence_rank(evidence) > evidence_rank(current):
                grouped[link.state_variable_id] = evidence

        return grouped

    def dependency_counts(self, *, db: Session, instance) -> dict[str, int]:
        counts: dict[str, int] = {}
        rows = list(
            db.scalars(
                select(CsmStateDependency).where(
                    CsmStateDependency.system_instance_id == instance.id,
                    CsmStateDependency.status == "active",
                )
            ).all()
        )

        for dependency in rows:
            counts[str(dependency.source_state_id)] = counts.get(str(dependency.source_state_id), 0) + 1
            counts[str(dependency.target_state_id)] = counts.get(str(dependency.target_state_id), 0) + 1

        return counts

    def merge_activation_candidates(
        self,
        *,
        state_candidates: list[dict],
        evidence_candidates: list[dict],
        route_mode: str,
    ) -> list[dict]:
        evidence_first = route_mode in {"exact_source", "evidence_first", "rare_detail", "correction_state"}
        primary = evidence_candidates if evidence_first else state_candidates
        secondary = state_candidates if evidence_first else evidence_candidates
        combined = sorted(primary, key=lambda item: item["score"], reverse=True)
        high_secondary = [item for item in secondary if item["score"] >= 0.10]

        if len([item for item in combined if item["score"] >= 0.10]) < settings.csm_activation_top_k:
            combined.extend(high_secondary)

        if not any(item["score"] >= 0.10 for item in combined):
            combined = (evidence_candidates if evidence_first else state_candidates)[:]
            combined.extend((state_candidates if evidence_first else evidence_candidates)[:])

        combined.sort(key=lambda item: (item["score"], 1 if item["kind"] == "state" else 0), reverse=True)
        deduped = []
        seen = set()

        for item in combined:
            evidence = item["evidence"]
            state = item["state"]
            key = (
                str(evidence.canonical_source_id)
                if evidence is not None
                else str(state.id)
                if state is not None
                else item["content"]
            )

            if key in seen and route_mode not in {"exact_source", "evidence_first"}:
                continue

            seen.add(key)
            deduped.append(item)

        return deduped

    def apply_dependency_metadata(self, *, db: Session, instance, state: CsmStateVariable, history: CsmStateHistory | None) -> None:
        dependency_ids = self.ensure_dependencies_for_state(db=db, instance=instance, state=state)
        value = dict(state.current_value or {})
        value["dependency_ids"] = dependency_ids
        state.current_value = value

        if history is not None:
            history_value = dict(history.new_value or {})
            history_value["dependency_ids"] = dependency_ids
            history.new_value = history_value

    def ensure_dependencies_for_state(self, *, db: Session, instance, state: CsmStateVariable) -> list[str]:
        related: list[tuple[float, str, CsmStateVariable]] = []
        state_terms = dependency_terms_for_state(state)
        if not state_terms:
            return []

        candidates = list(
            db.scalars(
                select(CsmStateVariable).where(
                    CsmStateVariable.system_instance_id == instance.id,
                    CsmStateVariable.id != state.id,
                    CsmStateVariable.status.in_(["active", "candidate"]),
                )
            ).all()
        )

        for other in candidates:
            other_terms = dependency_terms_for_state(other)
            if not other_terms:
                continue
            overlap = len(state_terms & other_terms) / max(1, min(len(state_terms), len(other_terms)))
            type_bonus, relation = dependency_type_bonus(state, other)
            weight = min(1.0, (overlap * 0.7) + type_bonus)

            if weight >= 0.20:
                related.append((weight, relation, other))

        related.sort(key=lambda item: item[0], reverse=True)
        dependency_ids: list[str] = []

        for weight, relation, other in related[:5]:
            dependency = db.scalar(
                select(CsmStateDependency).where(
                    CsmStateDependency.system_instance_id == instance.id,
                    CsmStateDependency.source_state_id == state.id,
                    CsmStateDependency.target_state_id == other.id,
                    CsmStateDependency.relation_type == relation,
                )
            )

            if dependency is None:
                dependency = CsmStateDependency(
                    system_instance_id=instance.id,
                    source_state_id=state.id,
                    target_state_id=other.id,
                    relation_type=relation,
                    weight=weight,
                    decay=0.0,
                    status="active",
                )
                db.add(dependency)
                db.flush()
            else:
                dependency.weight = max(dependency.weight, weight)
                dependency.status = "active"
                db.flush()

            dependency_ids.append(str(dependency.id))

        return dependency_ids


def evidence_type_for_source(source) -> str:
    if source.source_type == "patient_information":
        return f"structured_{source.source_subtype}"

    if source.source_type == "conversation":
        return "conversation_candidate_claim"

    return "document_candidate_material"


def verification_status_for_source(source) -> str:
    if source.source_type == "patient_information":
        return "verified"

    if source.source_type == "conversation":
        return "pending_review"

    if source.source_type == "document":
        return "candidate"

    return "candidate"


def confidence_for_source(source) -> float:
    if source.source_type == "patient_information":
        return 0.95

    if source.source_type == "document":
        return 0.65 if source.source_subtype in {"section", "page", "extracted_text"} else 0.5

    if source.source_type == "conversation":
        return 0.25

    return 0.4


def state_status_for_source(source) -> str:
    if source.source_type == "patient_information":
        return "active"

    if source.source_type == "document":
        return "candidate"

    return "pending_review"


def update_operator_for_source(source) -> str:
    if source.source_type == "patient_information":
        return "deterministic_latest_structured_source"

    if source.source_type == "document":
        return "document_candidate_state_extraction"

    return "conversation_pending_review"


def uncertainty_for_source(source) -> dict:
    if source.source_type == "patient_information":
        return {
            "extraction_confidence": 0.95,
            "source_reliability": 0.95,
            "posterior_uncertainty": 0.05,
            "epistemic_uncertainty": 0.02,
        }

    if source.source_type == "document":
        return {
            "extraction_confidence": 0.65,
            "source_reliability": 0.8,
            "posterior_uncertainty": 0.25,
            "epistemic_uncertainty": 0.15,
        }

    return {
        "extraction_confidence": 0.25,
        "source_reliability": 0.4,
        "posterior_uncertainty": 0.65,
        "epistemic_uncertainty": 0.45,
    }


def reason_for_source(source) -> str:
    if source.source_type == "patient_information":
        return "structured_patient_information_committed"

    if source.source_type == "document":
        return "document_candidate_evidence_ingested"

    return "conversation_proposal_requires_review"


def risk_level_for_source(source) -> str:
    high_risk_terms = ("allergy", "medication", "diagnosis", "treatment", "urgent", "discontinue")
    text = f"{source.source_subtype} {source.content_text}".lower()
    return "high" if any(term in text for term in high_risk_terms) else "medium"


def relation_for_evidence(evidence: CsmEvidence) -> str:
    if evidence.verification_status == "pending_review":
        return "derived_from"

    if evidence.verification_status == "candidate":
        return "qualifies"

    return "supports"


def normalized_state_value(source) -> Optional[str]:
    payload = source.structured_payload

    for key in ("name", "medication_name", "substance", "observation_name", "encounter_type", "title"):
        value = payload.get(key)

        if value:
            return str(value).lower()

    return None


def state_key_for_source(source) -> str:
    payload = source.structured_payload

    for key in ("name", "medication_name", "substance", "observation_name", "encounter_type", "title"):
        value = payload.get(key)

        if value:
            return str(value).strip().lower()

    return f"{source.source_subtype}:{source.source_record_id}"


def tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9]+", value.lower()))


def state_utility(query_terms: set[str], state: CsmStateVariable) -> float:
    state_terms = tokenize(f"{state.state_key} {state.current_value}")

    if not query_terms or not state_terms:
        return 0.0

    return len(query_terms & state_terms) / len(query_terms)


def evidence_rank(evidence: CsmEvidence) -> tuple[float, datetime]:
    return (
        float(evidence.confidence or 0.0),
        evidence.recorded_time or datetime.min.replace(tzinfo=timezone.utc),
    )


def dependency_terms_for_state(state: CsmStateVariable) -> set[str]:
    value = state.current_value or {}
    structured = value.get("structured") or {}
    text_parts = [
        state.state_key,
        state.state_type,
        str(value.get("value") or ""),
        str(value.get("raw_value") or ""),
    ]

    for key in (
        "name",
        "medication_name",
        "substance",
        "observation_name",
        "reason",
        "notes",
        "content",
        "title",
        "document_type",
        "interpretation",
    ):
        if structured.get(key):
            text_parts.append(str(structured[key]))

    stop_terms = {
        "active",
        "candidate",
        "clinical",
        "condition",
        "document",
        "evidence",
        "measurement",
        "medication",
        "note",
        "patient",
        "status",
        "the",
        "and",
        "with",
    }
    return {term for term in csm_v2_tokenize(" ".join(text_parts)) if len(term) > 2 and term not in stop_terms}


def dependency_type_bonus(source: CsmStateVariable, target: CsmStateVariable) -> tuple[float, str]:
    source_type = source.state_type
    target_type = target.state_type
    pair = {source_type, target_type}

    if pair == {"allergy", "medication"}:
        return 0.45, "allergy_medication_safety_dependency"
    if "medication" in pair and "condition" in pair:
        return 0.35, "medication_condition_dependency"
    if "measurement" in pair and ("condition" in pair or "clinical_note" in pair):
        return 0.35, "measurement_clinical_state_dependency"
    if "document" in pair or "section" in pair or "page" in pair or "extracted_text" in pair:
        return 0.20, "document_evidence_dependency"

    return 0.0, "lexical_state_dependency"
