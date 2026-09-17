from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.document.models import Document
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
from app.memory_systems.csm.v4_engine import (
    CSM_V4_IMPLEMENTATION_VERSION,
    CSM_V4_STATE_SCHEMA_VERSION,
    STATE_DEFINITIONS,
    allow_evidence_for_route_v4,
    allow_state_for_route_v4,
    build_measurement_trend_value,
    build_renal_function_value,
    build_state_value_payload_v4,
    build_superseded_previous_value,
    compact_evidence_context_v4,
    compact_state_context_v4,
    confidence_for_source_v4,
    evidence_type_for_source_v4,
    explicit_date_match,
    is_correction_source,
    late_arriving_temporal_match,
    is_renal_measurement_name,
    measurement_name_from_state,
    normalize_key,
    parse_iso,
    redundancy_key_for_evidence,
    redundancy_key_for_state,
    relation_for_transition,
    route_query_v4,
    score_evidence_v4,
    score_state_v4,
    state_definition_for_source,
    state_key_for_source_v4,
    tokenize,
    transition_operation_v4,
    verification_status_for_source_v4,
)


class CsmV4Adapter(MemorySystemAdapter):
    system_type = "csm_v4"

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
            "implementation_version": CSM_V4_IMPLEMENTATION_VERSION,
            "state_schema_version": CSM_V4_STATE_SCHEMA_VERSION,
            "state_engine": "evidence_derived_executable_state_v4",
            "query_router": "deterministic_decision_aware_router_v4",
            "context_contract": "compact_state_and_evidence_bundle_v4",
            "top_k_states": settings.csm_v4_top_k_states,
            "top_k_evidence": settings.csm_v4_top_k_evidence,
            "context_token_budget": settings.csm_v4_context_token_budget,
            "route_token_budgets": {
                "simple_state": settings.csm_v4_simple_state_token_budget,
                "ordinary": settings.csm_v4_ordinary_token_budget,
                "temporal_or_correction": settings.csm_v4_temporal_token_budget,
                "summary": settings.csm_v4_summary_token_budget,
            },
            "activation_threshold": settings.csm_v4_activation_threshold,
            "candidate_recall_limit": settings.csm_v4_candidate_recall_limit,
            "support_evidence_per_state": settings.csm_v4_support_evidence_per_state,
            "correction_evidence_per_state": settings.csm_v4_correction_evidence_per_state,
            "max_dependency_depth": settings.csm_v4_max_dependency_depth,
            "max_dependency_fanout": settings.csm_v4_max_dependency_fanout,
        }

    def ingest_sources(self, db: Session, *, instance, sources: list) -> list[IngestionResult]:
        results: list[IngestionResult] = []

        for source in sources:
            evidence = self.upsert_evidence(db=db, instance=instance, source=source)
            definition = state_definition_for_source(source)

            if source.source_type == "conversation":
                review = self.upsert_review_request(db=db, instance=instance, source=source, evidence=evidence)
                results.append(
                    IngestionResult(
                        native_record_type="csm_review_request",
                        native_record_id=review.id,
                        canonical_source_id=source.id,
                        source_hash=source.content_hash,
                        status="pending_review",
                    )
                )
                continue

            if definition is None:
                results.append(
                    IngestionResult(
                        native_record_type="csm_evidence",
                        native_record_id=evidence.id,
                        canonical_source_id=source.id,
                        source_hash=source.content_hash,
                        status="evidence_indexed",
                    )
                )
                continue

            state = self.upsert_state_from_evidence(
                db=db,
                instance=instance,
                source=source,
                evidence=evidence,
            )
            results.append(
                IngestionResult(
                    native_record_type="csm_state_variable",
                    native_record_id=state.id,
                    canonical_source_id=source.id,
                    source_hash=source.content_hash,
                    status="state_updated",
                )
            )

        return results

    def retrieve(self, db: Session, *, instance, query: str, top_k: int, token_budget: int, retrieval_mode):
        route = route_query_v4(query)
        query_terms = tokenize(query)
        cutoff_time = instance.source_cutoff_time
        effective_token_budget = self.route_token_budget(route=route, requested_token_budget=token_budget)
        states = list(
            db.scalars(
                select(CsmStateVariable).where(
                    CsmStateVariable.system_instance_id == instance.id,
                    CsmStateVariable.status.in_(["active", "candidate", "stale", "contested"]),
                )
            ).all()
        )
        evidence_by_state = self.evidence_by_state(db=db, states=states)
        evidences_by_state = self.evidences_by_state(db=db, states=states)
        dependency_counts = self.dependency_counts(db=db, instance=instance)
        candidate_audit = {
            "discarded": [],
            "redundancy_removals": [],
            "score_components": [],
        }
        seen_state_keys: set[str] = set()
        state_candidates = []

        for state in states:
            allowed, discard_reason = allow_state_for_route_v4(
                state=state,
                route=route,
                cutoff_time=cutoff_time,
            )
            if not allowed:
                candidate_audit["discarded"].append(
                    {
                        "kind": "state",
                        "id": str(state.id),
                        "reason": discard_reason,
                    }
                )
                continue

            redundancy_key = redundancy_key_for_state(state)
            redundant = redundancy_key in seen_state_keys
            seen_state_keys.add(redundancy_key)
            evidence = evidence_by_state.get(state.id)
            score, components, reason = score_state_v4(
                query=query,
                query_terms=query_terms,
                route=route,
                state=state,
                evidence=evidence,
                dependency_score=dependency_score_for_state(state, dependency_counts),
                cutoff_time=cutoff_time,
                redundant=redundant,
            )
            content = compact_state_context_v4(state=state, evidence=evidence, route=route, components=components)
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
                    "mandatory": self.is_mandatory_state(route=route, state=state, score=score, components=components),
                    "historical": False,
                }
            )
            candidate_audit["score_components"].append(
                {
                    "kind": "state",
                    "id": str(state.id),
                    "score": score,
                    "components": components,
                    "mandatory": state_candidates[-1]["mandatory"],
                }
            )

        history_candidates = self.history_candidates(
            db=db,
            instance=instance,
            query=query,
            query_terms=query_terms,
            route=route,
            cutoff_time=cutoff_time,
            states=states,
            evidence_by_state=evidence_by_state,
        )
        state_candidates.extend(history_candidates)
        evidence_candidates = []
        seen_evidence_keys: set[str] = set()
        evidence_rows = list(
            db.scalars(
                select(CsmEvidence).where(
                    CsmEvidence.system_instance_id == instance.id,
                    CsmEvidence.is_active.is_(True),
                )
            ).all()
        )

        for evidence in evidence_rows:
            allowed, discard_reason = allow_evidence_for_route_v4(
                evidence=evidence,
                route=route,
                cutoff_time=cutoff_time,
            )
            if not allowed:
                candidate_audit["discarded"].append(
                    {
                        "kind": "evidence",
                        "id": str(evidence.id),
                        "reason": discard_reason,
                    }
                )
                continue
            redundancy_key = redundancy_key_for_evidence(evidence)
            redundant = redundancy_key in seen_evidence_keys
            if redundant:
                candidate_audit["redundancy_removals"].append(
                    {
                        "kind": "evidence",
                        "id": str(evidence.id),
                        "key": redundancy_key,
                    }
                )
            seen_evidence_keys.add(redundancy_key)
            score, components, reason = score_evidence_v4(
                query=query,
                query_terms=query_terms,
                route=route,
                evidence=evidence,
                cutoff_time=cutoff_time,
                redundant=redundant,
            )
            content = compact_evidence_context_v4(evidence=evidence, route=route, components=components)
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
                    "mandatory": self.is_mandatory_evidence(route=route, evidence=evidence, score=score, components=components)
                    or self.is_temporal_date_evidence(route=route, query=query, evidence=evidence)
                    or self.is_late_arriving_temporal_evidence(route=route, query=query, evidence=evidence),
                    "historical": False,
                }
            )
            candidate_audit["score_components"].append(
                {
                    "kind": "evidence",
                    "id": str(evidence.id),
                    "score": score,
                    "components": components,
                    "mandatory": evidence_candidates[-1]["mandatory"],
                }
            )

        selected = self.select_activation_candidates(
            state_candidates=state_candidates,
            evidence_candidates=evidence_candidates,
            route_mode=route.mode,
            token_budget=effective_token_budget,
            evidence_by_state=evidences_by_state,
        )

        run = CsmActivationRun(
            system_instance_id=instance.id,
            conversation_id=None,
            query_text=query,
            token_budget=effective_token_budget,
            status="completed",
        )
        db.add(run)
        db.flush()
        self.persist_activation_audit(
            db=db,
            instance=instance,
            run=run,
            query=query,
            route=route,
            state_candidates=state_candidates,
            evidence_candidates=evidence_candidates,
            selected=selected,
            token_budget=effective_token_budget,
            candidate_audit=candidate_audit,
            retrieval_mode=retrieval_mode,
        )

        items: list[MemoryContextItem] = []
        added_activation_states: set[str] = set()

        for index, candidate in enumerate(selected, start=1):
            state = candidate["state"]
            evidence = candidate["evidence"]

            if state is not None and str(state.id) not in added_activation_states:
                added_activation_states.add(str(state.id))
                components = candidate["components"]
                db.add(
                    CsmActivationItem(
                        activation_run_id=run.id,
                        state_variable_id=state.id,
                        rank=index,
                        relevance_score=components.get("lexical_relevance", candidate["score"]),
                        dependency_score=components.get("dependency", 0),
                        confidence_score=components.get("state_confidence", state.confidence),
                        utility_score=candidate["score"],
                        estimated_token_cost=candidate["token_count"],
                        selected=True,
                        selection_reason=f"{candidate['reason']} route={route.mode} mandatory={candidate['mandatory']}",
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
                        "implementation_version": CSM_V4_IMPLEMENTATION_VERSION,
                        "route_mode": route.mode,
                        "route_reason": route.reason,
                        "route_features": route.features,
                        "mandatory": candidate["mandatory"],
                        "historical": candidate.get("historical", False),
                        "lineage_role": candidate.get("lineage_role"),
                        "route_budget": effective_token_budget,
                        "state_key": state.state_key if state is not None else None,
                        "state_version": state.current_version if state is not None else None,
                        "evidence_id": str(evidence.id) if evidence is not None else None,
                        "activation_components": candidate["components"],
                    },
                )
            )

        db.flush()
        budget = apply_token_budget(items, token_budget=effective_token_budget)
        mandatory_count = sum(1 for item in budget.included if item.metadata.get("mandatory"))
        result_limit = self.route_result_limit(route_mode=route.mode, top_k=top_k, mandatory_count=mandatory_count)
        warnings = [
            (
                f"CSM v4 route={route.mode}; selected {len(selected)} items from "
                f"{len(state_candidates) + len(evidence_candidates)} valid candidates using mandatory+top-k activation."
            )
        ]
        return budget.included[:result_limit], warnings, "ready"

    def route_result_limit(self, *, route_mode: str, top_k: int, mandatory_count: int) -> int:
        if route_mode in {"correction_state", "temporal_state"}:
            return max(top_k, mandatory_count, settings.csm_v4_candidate_recall_limit)
        if route_mode in {"exact_source", "rare_detail", "evidence_first"}:
            return max(top_k, mandatory_count, settings.csm_v4_top_k_evidence, settings.csm_v4_candidate_recall_limit // 2)
        if route_mode == "hybrid_state_evidence":
            return max(top_k, mandatory_count, settings.csm_v4_top_k_states + settings.csm_v4_top_k_evidence)
        if route_mode in {"dependency_state", "high_risk_review", "decision_state"}:
            return max(top_k, mandatory_count, settings.csm_v4_top_k_states + max(2, settings.csm_v4_top_k_evidence // 2))
        return max(top_k, mandatory_count)

    def route_token_budget(self, *, route, requested_token_budget: int) -> int:
        route_budget = {
            "state_first": settings.csm_v4_simple_state_token_budget,
            "decision_state": settings.csm_v4_ordinary_token_budget,
            "high_risk_review": settings.csm_v4_ordinary_token_budget,
            "evidence_first": settings.csm_v4_ordinary_token_budget,
            "exact_source": settings.csm_v4_ordinary_token_budget,
            "rare_detail": settings.csm_v4_ordinary_token_budget,
            "dependency_state": settings.csm_v4_temporal_token_budget,
            "temporal_state": settings.csm_v4_temporal_token_budget,
            "correction_state": settings.csm_v4_temporal_token_budget,
            "hybrid_state_evidence": settings.csm_v4_summary_token_budget,
        }.get(route.mode, settings.csm_v4_ordinary_token_budget)
        return min(requested_token_budget, settings.csm_v4_context_token_budget, route_budget)

    def get_statistics(self, db: Session, *, instance) -> dict:
        evidence = db.scalar(
            select(func.count()).select_from(CsmEvidence).where(
                CsmEvidence.system_instance_id == instance.id,
                CsmEvidence.is_active.is_(True),
            )
        )
        states = db.scalar(
            select(func.count()).select_from(CsmStateVariable).where(
                CsmStateVariable.system_instance_id == instance.id,
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
            "state_schema_registry": sorted(STATE_DEFINITIONS),
            "document_extraction": "evidence_only",
            "conversation_claim_extraction": "candidate_review_only",
            "answer_llm_can_mutate_state": False,
        }

    def upsert_evidence(self, *, db: Session, instance, source) -> CsmEvidence:
        evidence_type = evidence_type_for_source_v4(source)
        evidence = db.scalar(
            select(CsmEvidence).where(
                CsmEvidence.system_instance_id == instance.id,
                CsmEvidence.canonical_source_id == source.id,
                CsmEvidence.evidence_type == evidence_type,
            )
        )
        if evidence is not None:
            return evidence

        recorded_time = evidence_recorded_time_v4(db=db, source=source)
        evidence = CsmEvidence(
            system_instance_id=instance.id,
            canonical_source_id=source.id,
            evidence_type=evidence_type,
            observation_type=source.source_subtype,
            content=source.content_text,
            structured_value={
                **(source.structured_payload or {}),
                "csm_implementation_version": CSM_V4_IMPLEMENTATION_VERSION,
                "csm_v4_lifecycle": "current",
                "csm_v4_available_time": recorded_time.isoformat() if recorded_time else None,
                "immutable_evidence": True,
            },
            normalized_value=normalized_evidence_value(source),
            unit=(source.structured_payload or {}).get("unit"),
            source_type=source.source_type,
            document_id=source.document_id,
            page_number=source.page_number,
            section_id=source.section_id,
            conversation_id=source.conversation_id,
            message_id=source.message_id,
            valid_time=source.valid_time,
            recorded_time=recorded_time,
            confidence=confidence_for_source_v4(source),
            verification_status=verification_status_for_source_v4(source),
            extraction_method="deterministic_evidence_canonicalization_v4",
            extractor_version="3",
            is_active=True,
        )
        db.add(evidence)
        db.flush()
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
            "implementation_version": CSM_V4_IMPLEMENTATION_VERSION,
            "policy": "conversation_claims_never_become_verified_state_without_review",
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
                risk_level=risk_level_for_text(f"{source.source_subtype} {source.content_text}"),
                status="pending",
            )
            db.add(review)
            db.flush()
        elif review.status == "pending":
            review.proposed_claim = source.content_text
            review.proposed_value = proposed_value
            review.support_status = "insufficient_evidence"
            review.risk_level = risk_level_for_text(f"{source.source_subtype} {source.content_text}")
            db.flush()

        return review

    def upsert_state_from_evidence(self, *, db: Session, instance, source, evidence: CsmEvidence) -> CsmStateVariable:
        definition = state_definition_for_source(source)
        if definition is None:
            raise ValueError("CSM v4 state upsert requires a registered computational state definition.")

        state_key = state_key_for_source_v4(source)
        now = datetime.now(timezone.utc)
        state = db.scalar(
            select(CsmStateVariable).where(
                CsmStateVariable.system_instance_id == instance.id,
                CsmStateVariable.state_type == definition.state_type,
                CsmStateVariable.state_key == state_key,
            )
        )
        previous_value = state.current_value if state is not None else None

        if previous_value and (previous_value.get("lineage") or {}).get("source_hash") == source.content_hash:
            self.ensure_evidence_link(db=db, state=state, evidence=evidence, relation="SUPPORTS")
            db.flush()
            return state

        operation = transition_operation_v4(previous_value=previous_value, source=source, evidence=evidence)
        current_version = 1 if state is None else state.current_version + 1
        supersedes = list((previous_value or {}).get("evidence_ids") or []) if operation in {"supersede", "correct"} else []
        new_value = build_state_value_payload_v4(
            source=source,
            evidence=evidence,
            definition=definition,
            operation=operation,
            version=current_version,
            previous_value=previous_value,
            supersedes=supersedes,
            dependency_ids=[],
        )
        status = state_status_from_value(new_value)
        update_event = CsmUpdateEvent(
            system_instance_id=instance.id,
            trigger_source_id=source.id,
            event_type="state_transition",
            operator=definition.update_operator,
            input_snapshot={
                "canonical_source_id": str(source.id),
                "content_hash": source.content_hash,
                "previous_state_id": str(state.id) if state is not None else None,
                "previous_version": state.current_version if state is not None else None,
            },
            output_snapshot={
                "state_key": state_key,
                "state_type": definition.state_type,
                "operation": operation,
                "schema_version": CSM_V4_STATE_SCHEMA_VERSION,
                "supersedes": supersedes,
                "status": status,
                "implementation_version": CSM_V4_IMPLEMENTATION_VERSION,
            },
            status="completed",
        )
        db.add(update_event)
        db.flush()

        if state is None:
            state = CsmStateVariable(
                system_instance_id=instance.id,
                state_type=definition.state_type,
                state_key=state_key,
                current_value=new_value,
                confidence=evidence.confidence,
                uncertainty=new_value["uncertainty_components"],
                trend=None,
                prediction=None,
                status=status,
                valid_from=source.valid_time,
                valid_to=None,
                current_version=1,
                update_operator=definition.update_operator,
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
                update_reason=new_value["transition"]["reason"],
                valid_from=source.valid_time,
                valid_to=None,
                update_event_id=update_event.id,
            )
            db.add(history)
        else:
            previous_confidence = state.confidence
            history_previous_value = build_superseded_previous_value(
                previous_value,
                evidence_id=str(evidence.id),
                operation=operation,
            )
            state.current_value = new_value
            state.confidence = max(0.0, min(1.0, (state.confidence * 0.30) + (evidence.confidence * 0.70)))
            state.current_version = current_version
            state.status = status
            state.uncertainty = new_value["uncertainty_components"]
            state.update_operator = definition.update_operator
            state.valid_from = source.valid_time or state.valid_from
            state.last_updated_at = now
            db.flush()
            history = CsmStateHistory(
                state_variable_id=state.id,
                version_number=state.current_version,
                previous_value=history_previous_value,
                new_value=new_value,
                previous_confidence=previous_confidence,
                new_confidence=state.confidence,
                update_reason=new_value["transition"]["reason"],
                valid_from=source.valid_time,
                valid_to=None,
                update_event_id=update_event.id,
            )
            db.add(history)

        self.ensure_evidence_link(db=db, state=state, evidence=evidence, relation=relation_for_transition(operation, evidence))
        self.apply_dependency_metadata(db=db, instance=instance, state=state, history=history)
        self.recompute_derived_descendants(db=db, instance=instance, parent_state=state, triggering_evidence=evidence)
        db.flush()
        return state

    def ensure_evidence_link(self, *, db: Session, state: CsmStateVariable, evidence: CsmEvidence, relation: str) -> None:
        link = db.get(CsmStateEvidenceLink, {"state_variable_id": state.id, "evidence_id": evidence.id})
        if link is None:
            db.add(
                CsmStateEvidenceLink(
                    state_variable_id=state.id,
                    evidence_id=evidence.id,
                    contribution_type=relation,
                    contribution_weight=1.0,
                )
            )
        elif link.contribution_type != relation:
            link.contribution_type = relation
            db.flush()

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
            if current is None or evidence_rank_v4(evidence, link.contribution_type) > evidence_rank_v4(current, ""):
                grouped[link.state_variable_id] = evidence

        return grouped

    def evidences_by_state(self, *, db: Session, states: list[CsmStateVariable]) -> dict:
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
            grouped.setdefault(link.state_variable_id, []).append((link, evidence))
        for state_id, linked in grouped.items():
            linked.sort(key=lambda item: evidence_rank_v4(item[1], item[0].contribution_type), reverse=True)
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
        dependency_ids: list[str] = []
        candidates = list(
            db.scalars(
                select(CsmStateVariable).where(
                    CsmStateVariable.system_instance_id == instance.id,
                    CsmStateVariable.id != state.id,
                    CsmStateVariable.status.in_(["active", "candidate", "stale", "contested"]),
                )
            ).all()
        )
        for other in candidates:
            relation, weight = controlled_dependency_relation(state, other)
            if not relation or weight <= 0:
                continue
            dependency = self.upsert_dependency(
                db=db,
                instance=instance,
                source_state=state,
                target_state=other,
                relation=relation,
                weight=weight,
            )
            dependency_ids.append(str(dependency.id))
            if len(dependency_ids) >= settings.csm_v4_max_dependency_fanout:
                break
        return dependency_ids

    def upsert_dependency(self, *, db: Session, instance, source_state: CsmStateVariable, target_state: CsmStateVariable, relation: str, weight: float) -> CsmStateDependency:
        dependency = db.scalar(
            select(CsmStateDependency).where(
                CsmStateDependency.system_instance_id == instance.id,
                CsmStateDependency.source_state_id == source_state.id,
                CsmStateDependency.target_state_id == target_state.id,
                CsmStateDependency.relation_type == relation,
            )
        )
        if dependency is None:
            dependency = CsmStateDependency(
                system_instance_id=instance.id,
                source_state_id=source_state.id,
                target_state_id=target_state.id,
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
        return dependency

    def recompute_derived_descendants(self, *, db: Session, instance, parent_state: CsmStateVariable, triggering_evidence: CsmEvidence) -> None:
        if parent_state.state_type != "measurement":
            return

        histories = list(
            db.scalars(
                select(CsmStateHistory)
                .where(CsmStateHistory.state_variable_id == parent_state.id)
                .order_by(CsmStateHistory.version_number.asc())
            ).all()
        )
        trend_value = build_measurement_trend_value(parent_state, histories)
        trend_state = None
        if trend_value is not None:
            trend_state = self.upsert_derived_state(
                db=db,
                instance=instance,
                parent_state=parent_state,
                evidence=triggering_evidence,
                state_type="measurement_trend",
                state_key=f"measurement_trend:{normalize_key(measurement_name_from_state(parent_state))}",
                value=trend_value,
                relation="derived_measurement_trend",
            )
            self.upsert_dependency(
                db=db,
                instance=instance,
                source_state=parent_state,
                target_state=trend_state,
                relation="measurement_parent_to_trend",
                weight=1.0,
            )

        renal_value = build_renal_function_value(parent_state, trend_value)
        if renal_value is not None:
            renal_state = self.upsert_derived_state(
                db=db,
                instance=instance,
                parent_state=parent_state,
                evidence=triggering_evidence,
                state_type="renal_function",
                state_key="renal_function:kidney_function",
                value=renal_value,
                relation="derived_renal_function",
            )
            self.upsert_dependency(
                db=db,
                instance=instance,
                source_state=parent_state,
                target_state=renal_state,
                relation="renal_measurement_parent_to_renal_function",
                weight=1.0,
            )
            if trend_state is not None:
                self.upsert_dependency(
                    db=db,
                    instance=instance,
                    source_state=trend_state,
                    target_state=renal_state,
                    relation="renal_trend_parent_to_renal_function",
                    weight=0.85,
                )

    def upsert_derived_state(
        self,
        *,
        db: Session,
        instance,
        parent_state: CsmStateVariable,
        evidence: CsmEvidence,
        state_type: str,
        state_key: str,
        value: dict,
        relation: str,
    ) -> CsmStateVariable:
        definition = STATE_DEFINITIONS[state_type]
        now = datetime.now(timezone.utc)
        state = db.scalar(
            select(CsmStateVariable).where(
                CsmStateVariable.system_instance_id == instance.id,
                CsmStateVariable.state_type == state_type,
                CsmStateVariable.state_key == state_key,
            )
        )
        previous_value = state.current_value if state is not None else None
        current_version = 1 if state is None else state.current_version + 1
        parent_value = parent_state.current_value or {}
        derived_value = {
            "schema_version": CSM_V4_STATE_SCHEMA_VERSION,
            "implementation_version": CSM_V4_IMPLEMENTATION_VERSION,
            "state_identity": {
                "state_type": state_type,
                "semantic_type": definition.semantic_type,
                "state_key": state_key,
                "source_subtype": "derived",
            },
            "value": value,
            "raw_value": value.get("display") or str(value),
            "structured": value,
            "unit": value.get("unit"),
            "status": "active" if parent_state.status == "active" else "stale",
            "valid_time": value.get("latest_valid_time") or value.get("valid_time") or parent_value.get("valid_time"),
            "recorded_time": now.isoformat(),
            "event_time": value.get("latest_valid_time") or parent_value.get("event_time"),
            "recorded_source_ids": sorted(set(parent_value.get("recorded_source_ids") or [])),
            "evidence_ids": sorted(set(parent_value.get("evidence_ids") or [str(evidence.id)])),
            "support_evidence_ids": sorted(set(parent_value.get("support_evidence_ids") or [str(evidence.id)])),
            "correction_evidence_ids": sorted(set(parent_value.get("correction_evidence_ids") or [])),
            "lineage": {
                "latest_canonical_source_id": str(evidence.canonical_source_id),
                "latest_evidence_id": str(evidence.id),
                "parent_state_id": str(parent_state.id),
                "source_hash": (parent_value.get("lineage") or {}).get("source_hash"),
                "source_type": "derived_state",
                "source_subtype": state_type,
            },
            "relations": {
                "incoming_relation": "SUPPORTS",
                "supports": sorted(set(parent_value.get("support_evidence_ids") or [str(evidence.id)])),
                "corrects": sorted(set(parent_value.get("correction_evidence_ids") or [])),
                "supersedes": list((previous_value or {}).get("evidence_ids") or []),
                "superseded_by": [],
            },
            "confidence_components": {
                "source_confidence": float(parent_state.confidence or 0.0),
                "verification_quality": 0.86,
                "structure_quality": 1.0,
                "operator_quality": 0.86,
            },
            "uncertainty_components": {
                "posterior_uncertainty": max(0.05, min(0.35, 1.0 - float(parent_state.confidence or 0.0))),
                "verification_uncertainty": 0.14,
                "temporal_uncertainty": 0.05,
                "lifecycle_uncertainty": 0.08 if parent_state.status == "active" else 0.25,
            },
            "dependency_ids": [],
            "transition": {
                "operation": "derived_recompute",
                "operator": definition.update_operator,
                "reason": f"{definition.update_operator}:bounded_parent_recompute",
                "previous_version": current_version - 1 if current_version > 1 else None,
                "new_version": current_version,
                "valid_time": value.get("latest_valid_time") or value.get("valid_time") or parent_value.get("valid_time"),
                "recorded_time": now.isoformat(),
            },
            "audit": {
                "updated_at": now.isoformat(),
                "state_schema_registry": "explicit_state_definitions_v4",
                "parent_state_id": str(parent_state.id),
                "dependency_relation": relation,
                "max_dependency_depth": settings.csm_v4_max_dependency_depth,
                "llm_mutable": False,
            },
        }
        update_event = CsmUpdateEvent(
            system_instance_id=instance.id,
            trigger_source_id=evidence.canonical_source_id,
            event_type="derived_state_recompute",
            operator=definition.update_operator,
            input_snapshot={
                "parent_state_id": str(parent_state.id),
                "parent_state_version": parent_state.current_version,
                "previous_derived_state_id": str(state.id) if state is not None else None,
            },
            output_snapshot={
                "state_key": state_key,
                "state_type": state_type,
                "operation": "derived_recompute",
                "implementation_version": CSM_V4_IMPLEMENTATION_VERSION,
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
                current_value=derived_value,
                confidence=max(0.0, min(1.0, float(parent_state.confidence or 0.0) * 0.92)),
                uncertainty=derived_value["uncertainty_components"],
                trend=value if state_type == "measurement_trend" else None,
                prediction=None,
                status=derived_value["status"],
                valid_from=parse_iso(derived_value.get("valid_time")),
                valid_to=None,
                current_version=1,
                update_operator=definition.update_operator,
                last_updated_at=now,
            )
            db.add(state)
            db.flush()
            history = CsmStateHistory(
                state_variable_id=state.id,
                version_number=state.current_version,
                previous_value=None,
                new_value=derived_value,
                previous_confidence=None,
                new_confidence=state.confidence,
                update_reason=derived_value["transition"]["reason"],
                valid_from=state.valid_from,
                valid_to=None,
                update_event_id=update_event.id,
            )
            db.add(history)
        elif previous_value != derived_value:
            previous_confidence = state.confidence
            state.current_value = derived_value
            state.confidence = max(0.0, min(1.0, (state.confidence * 0.20) + (float(parent_state.confidence or 0.0) * 0.80)))
            state.current_version = current_version
            state.status = derived_value["status"]
            state.uncertainty = derived_value["uncertainty_components"]
            state.trend = value if state_type == "measurement_trend" else state.trend
            state.update_operator = definition.update_operator
            state.last_updated_at = now
            db.flush()
            history = CsmStateHistory(
                state_variable_id=state.id,
                version_number=state.current_version,
                previous_value=build_superseded_previous_value(previous_value, evidence_id=str(evidence.id), operation="supersede"),
                new_value=derived_value,
                previous_confidence=previous_confidence,
                new_confidence=state.confidence,
                update_reason=derived_value["transition"]["reason"],
                valid_from=state.valid_from,
                valid_to=None,
                update_event_id=update_event.id,
            )
            db.add(history)

        self.ensure_evidence_link(db=db, state=state, evidence=evidence, relation="SUPPORTS")
        return state

    def history_candidates(
        self,
        *,
        db: Session,
        instance,
        query: str,
        query_terms: set[str],
        route,
        cutoff_time: Optional[datetime],
        states: list[CsmStateVariable],
        evidence_by_state: dict,
    ) -> list[dict]:
        if not route.include_historical:
            return []

        by_id = {state.id: state for state in states}
        rows = list(
            db.scalars(
                select(CsmStateHistory)
                .where(CsmStateHistory.state_variable_id.in_(list(by_id)))
                .order_by(CsmStateHistory.created_at.asc())
            ).all()
        )
        candidates = []
        for history in rows:
            state = by_id.get(history.state_variable_id)
            if state is None:
                continue
            value = history.previous_value if route.mode == "correction_state" and history.previous_value else history.new_value
            if not value or value.get("implementation_version") != CSM_V4_IMPLEMENTATION_VERSION:
                continue
            recorded = parse_iso(value.get("recorded_time"))
            if cutoff_time and recorded and recorded > cutoff_time:
                continue
            evidence = evidence_by_state.get(state.id)
            score, components, reason = score_state_v4(
                query=query,
                query_terms=query_terms,
                route=route,
                state=state,
                evidence=evidence,
                dependency_score=0.0,
                cutoff_time=cutoff_time,
                historical=True,
            )
            content = compact_state_context_v4(
                state=state,
                evidence=evidence,
                route=route,
                components=components,
                historical_value=value,
            )
            candidates.append(
                {
                    "kind": "state_history",
                    "state": state,
                    "evidence": evidence,
                    "score": score,
                    "components": components,
                    "reason": f"historical_{reason}",
                    "content": content,
                    "token_count": estimate_tokens(content),
                    "mandatory": route.mode == "correction_state" and str(value.get("status")).lower() == "superseded",
                    "historical": True,
                }
            )
        return candidates

    def is_mandatory_state(self, *, route, state: CsmStateVariable, score: float, components: dict) -> bool:
        if route.mode == "correction_state":
            return state.state_type in route.preferred_state_types and score >= settings.csm_v4_activation_threshold
        if route.mode == "high_risk_review":
            return state.state_type in {"allergy", "medication", "condition"} and score >= settings.csm_v4_activation_threshold
        if route.mode == "dependency_state":
            return components.get("dependency", 0) > 0 or state.state_type in route.preferred_state_types
        if route.mode in {"state_first", "decision_state", "hybrid_state_evidence"}:
            return state.state_type in route.preferred_state_types and score >= settings.csm_v4_activation_threshold
        return False

    def is_mandatory_evidence(self, *, route, evidence: CsmEvidence, score: float, components: dict) -> bool:
        if route.mode in {"exact_source", "evidence_first", "rare_detail"}:
            return score >= settings.csm_v4_activation_threshold
        if route.mode == "correction_state":
            lifecycle = str(evidence.structured_value.get("csm_v4_lifecycle") or "")
            return is_correction_evidence(evidence) or lifecycle in {"correction", "superseded"}
        return False

    def is_temporal_date_evidence(self, *, route, query: str, evidence: CsmEvidence) -> bool:
        return (
            route.mode == "temporal_state"
            and evidence.source_type == "document"
            and explicit_date_match(query, evidence.valid_time)
        )

    def is_late_arriving_temporal_evidence(self, *, route, query: str, evidence: CsmEvidence) -> bool:
        return route.mode == "temporal_state" and late_arriving_temporal_match(query, evidence.valid_time, evidence.recorded_time)

    def select_activation_candidates(
        self,
        *,
        state_candidates: list[dict],
        evidence_candidates: list[dict],
        route_mode: str,
        token_budget: int,
        evidence_by_state: dict | None = None,
    ) -> list[dict]:
        mandatory = [candidate for candidate in state_candidates + evidence_candidates if candidate["mandatory"]]
        mandatory.sort(key=lambda item: item["score"], reverse=True)

        optional_states = [candidate for candidate in state_candidates if not candidate["mandatory"]]
        optional_evidence = [candidate for candidate in evidence_candidates if not candidate["mandatory"]]
        optional_states.sort(key=lambda item: item["score"], reverse=True)
        optional_evidence.sort(key=lambda item: item["score"], reverse=True)

        selected = []
        selected_keys: set[str] = set()
        used_tokens = 0

        def add_candidate(candidate: dict) -> None:
            nonlocal used_tokens
            key = selection_key(candidate)
            if key in selected_keys and route_mode not in {"exact_source", "correction_state"}:
                return
            if used_tokens + candidate["token_count"] > token_budget and selected:
                return
            selected_keys.add(key)
            selected.append(candidate)
            used_tokens += candidate["token_count"]

        for candidate in mandatory:
            if route_mode == "correction_state" and candidate.get("evidence") is not None and is_correction_evidence(candidate["evidence"]):
                candidate.setdefault("lineage_role", "mandatory_correction_evidence")
            else:
                candidate.setdefault("lineage_role", "route_mandatory")
            add_candidate(candidate)

        state_recall_limit = max(settings.csm_v4_top_k_states, settings.csm_v4_candidate_recall_limit // 2)
        for candidate in optional_states[:state_recall_limit]:
            if candidate["score"] >= settings.csm_v4_activation_threshold:
                candidate.setdefault("lineage_role", "stage_b_selected_state")
                add_candidate(candidate)
            if len([item for item in selected if item["state"] is not None]) >= settings.csm_v4_top_k_states:
                break

        self.add_support_evidence_for_selected_states(
            selected=selected,
            evidence_candidates=evidence_candidates,
            evidence_by_state=evidence_by_state or {},
            route_mode=route_mode,
            add_candidate=add_candidate,
        )

        evidence_limit = self.optional_evidence_limit(route_mode)
        for candidate in optional_evidence[: max(evidence_limit, settings.csm_v4_candidate_recall_limit // 2)]:
            if candidate["score"] >= settings.csm_v4_activation_threshold:
                candidate.setdefault("lineage_role", "adaptive_evidence_fallback")
                add_candidate(candidate)
            if len([item for item in selected if item["evidence"] is not None and item["state"] is None]) >= evidence_limit:
                break

        if route_mode == "dependency_state":
            for candidate in optional_states:
                if candidate in selected:
                    continue
                if candidate["components"].get("dependency", 0.0) > 0:
                    candidate["mandatory"] = True
                    candidate["lineage_role"] = "dependency_expansion"
                    add_candidate(candidate)

        if not selected and evidence_candidates:
            evidence_candidates[0].setdefault("lineage_role", "empty_result_evidence_fallback")
            add_candidate(sorted(evidence_candidates, key=lambda item: item["score"], reverse=True)[0])
        elif not selected and state_candidates:
            state_candidates[0].setdefault("lineage_role", "empty_result_state_fallback")
            add_candidate(sorted(state_candidates, key=lambda item: item["score"], reverse=True)[0])

        selected.sort(key=lambda item: (0 if item["mandatory"] else 1, -item["score"], 0 if item["kind"].startswith("state") else 1))
        return selected

    def add_support_evidence_for_selected_states(
        self,
        *,
        selected: list[dict],
        evidence_candidates: list[dict],
        evidence_by_state: dict,
        route_mode: str,
        add_candidate,
    ) -> None:
        by_evidence_id = {
            str(candidate["evidence"].id): candidate
            for candidate in evidence_candidates
            if candidate.get("evidence") is not None
        }
        limit = self.support_evidence_limit(route_mode)
        selected_states = [candidate for candidate in list(selected) if candidate.get("state") is not None]
        for state_candidate in selected_states:
            state = state_candidate["state"]
            linked = evidence_by_state.get(state.id, [])
            support_added = 0
            for link, evidence in linked:
                evidence_candidate = by_evidence_id.get(str(evidence.id))
                if evidence_candidate is None:
                    continue
                relation = str(link.contribution_type or "").upper()
                if support_added >= limit and relation not in {"CORRECTS", "CONTRADICTS", "SUPERSEDES"}:
                    continue
                evidence_candidate["mandatory"] = True
                evidence_candidate["lineage_role"] = self.lineage_role_for_relation(relation, route_mode)
                add_candidate(evidence_candidate)
                support_added += 1

    def support_evidence_limit(self, route_mode: str) -> int:
        if route_mode in {"correction_state", "temporal_state"}:
            return settings.csm_v4_correction_evidence_per_state
        if route_mode in {"exact_source", "rare_detail", "evidence_first", "dependency_state"}:
            return max(settings.csm_v4_support_evidence_per_state, 2)
        return settings.csm_v4_support_evidence_per_state

    def optional_evidence_limit(self, route_mode: str) -> int:
        if route_mode in {"correction_state", "temporal_state", "hybrid_state_evidence"}:
            return settings.csm_v4_top_k_evidence
        if route_mode in {"exact_source", "rare_detail", "evidence_first"}:
            return max(settings.csm_v4_top_k_evidence, settings.csm_v4_candidate_recall_limit // 2)
        return max(2, settings.csm_v4_top_k_evidence // 2)

    def lineage_role_for_relation(self, relation: str, route_mode: str) -> str:
        if route_mode == "correction_state" and relation in {"CORRECTS", "SUPERSEDES"}:
            return "mandatory_correction_evidence"
        if relation == "CONTRADICTS":
            return "mandatory_contested_evidence"
        if relation == "CORRECTS":
            return "mandatory_correction_evidence"
        return "mandatory_state_support_evidence"

    def persist_activation_audit(
        self,
        *,
        db: Session,
        instance,
        run: CsmActivationRun,
        query: str,
        route,
        state_candidates: list[dict],
        evidence_candidates: list[dict],
        selected: list[dict],
        token_budget: int,
        candidate_audit: dict,
        retrieval_mode,
    ) -> None:
        selected_states = [candidate for candidate in selected if candidate["state"] is not None]
        selected_evidence = [candidate for candidate in selected if candidate["evidence"] is not None]
        db.add(
            CsmUpdateEvent(
                system_instance_id=instance.id,
                trigger_source_id=None,
                event_type="activation_audit",
                operator="deterministic_csm_v4_activation",
                input_snapshot={
                    "query": query,
                    "retrieval_mode": retrieval_mode,
                    "source_cutoff_time": instance.source_cutoff_time.isoformat() if instance.source_cutoff_time else None,
                },
                output_snapshot={
                    "implementation_version": CSM_V4_IMPLEMENTATION_VERSION,
                    "activation_run_id": str(run.id),
                    "route": route.mode,
                    "route_reason": route.reason,
                    "route_features": route.features,
                    "mandatory_policy": route.mandatory_policy,
                    "total_candidates": len(state_candidates) + len(evidence_candidates) + len(candidate_audit.get("discarded", [])),
                    "valid_candidates": len(state_candidates) + len(evidence_candidates),
                    "mandatory_count": sum(1 for candidate in state_candidates + evidence_candidates if candidate["mandatory"]),
                    "optional_candidate_count": sum(1 for candidate in state_candidates + evidence_candidates if not candidate["mandatory"]),
                    "selected_state_count": len(selected_states),
                    "selected_evidence_count": len(selected_evidence),
                    "top_k_states": settings.csm_v4_top_k_states,
                    "top_k_evidence": settings.csm_v4_top_k_evidence,
                    "candidate_recall_limit": settings.csm_v4_candidate_recall_limit,
                    "support_evidence_per_state": settings.csm_v4_support_evidence_per_state,
                    "correction_evidence_per_state": settings.csm_v4_correction_evidence_per_state,
                    "token_budget": token_budget,
                    "estimated_serialized_tokens": sum(candidate["token_count"] for candidate in selected),
                    "state_ids_selected": [str(candidate["state"].id) for candidate in selected_states],
                    "state_versions_selected": [
                        candidate["state"].current_version for candidate in selected_states
                    ],
                    "supporting_evidence_ids": [
                        str(candidate["evidence"].id)
                        for candidate in selected_evidence
                        if candidate["evidence"] is not None
                    ],
                    "lineage_roles": [
                        {
                            "kind": candidate["kind"],
                            "state_id": str(candidate["state"].id) if candidate["state"] is not None else None,
                            "evidence_id": str(candidate["evidence"].id) if candidate["evidence"] is not None else None,
                            "canonical_source_id": str(candidate["evidence"].canonical_source_id) if candidate["evidence"] is not None else None,
                            "lineage_role": candidate.get("lineage_role"),
                        }
                        for candidate in selected
                    ],
                    "utility_components": candidate_audit.get("score_components", []),
                    "discarded_candidates": candidate_audit.get("discarded", []),
                    "redundancy_removals": candidate_audit.get("redundancy_removals", []),
                    "fallback_reason": "best_evidence_or_state_fallback" if not selected else None,
                    "context_ordering": [
                        {
                            "rank": index,
                            "kind": candidate["kind"],
                            "score": candidate["score"],
                            "mandatory": candidate["mandatory"],
                        }
                        for index, candidate in enumerate(selected, start=1)
                    ],
                },
                status="completed",
            )
        )


def normalized_evidence_value(source) -> Optional[str]:
    payload = source.structured_payload or {}
    for key in ("name", "medication_name", "generic_name", "substance", "observation_name", "encounter_type", "title", "original_filename", "document_type"):
        value = payload.get(key)
        if value:
            return normalize_key(value)
    return normalize_key(source_preview(source.content_text, max_length=120)) if source.content_text else None


def evidence_recorded_time_v4(*, db: Session, source) -> datetime:
    if source.source_type == "document" and source.source_subtype in {"section", "page", "extracted_text"} and source.document_id:
        document = db.get(Document, source.document_id)
        if document is not None and document.created_at is not None:
            return document.created_at
    return source.recorded_time


def state_status_from_value(value: dict) -> str:
    status = str(value.get("status") or "").lower()
    if status in {"contested", "pending_review", "unverified"}:
        return "contested" if status == "contested" else "candidate"
    if status in {"inactive", "resolved"}:
        return "active"
    if status == "superseded":
        return "stale"
    return "active"


def evidence_rank_v4(evidence: CsmEvidence, relation: str) -> tuple[float, float, datetime]:
    relation_bonus = {
        "SUPPORTS": 1.0,
        "CORRECTS": 0.95,
        "SUPERSEDES": 0.90,
        "QUALIFIES": 0.65,
        "CONTRADICTS": 0.60,
    }.get(relation, 0.50)
    return (
        relation_bonus,
        float(evidence.confidence or 0.0),
        evidence.recorded_time or datetime.min.replace(tzinfo=timezone.utc),
    )


def dependency_score_for_state(state: CsmStateVariable, dependency_counts: dict[str, int]) -> float:
    count = dependency_counts.get(str(state.id), 0)
    return min(1.0, count / 3)


def controlled_dependency_relation(source: CsmStateVariable, target: CsmStateVariable) -> tuple[Optional[str], float]:
    if source.state_type == "measurement" and target.state_type == "measurement_trend":
        source_name = normalize_key(measurement_name_from_state(source))
        if target.state_key.endswith(source_name):
            return "measurement_parent_to_trend", 1.0
    if source.state_type == "measurement" and target.state_type == "renal_function" and is_renal_measurement_name(measurement_name_from_state(source)):
        return "renal_measurement_parent_to_renal_function", 1.0
    if {source.state_type, target.state_type} == {"allergy", "medication"}:
        overlap = name_overlap(source, target)
        if overlap > 0:
            return "allergy_medication_same_substance", min(1.0, 0.45 + overlap)
    if {source.state_type, target.state_type} == {"condition", "medication"}:
        overlap = name_overlap(source, target)
        if overlap >= 0.20:
            return "medication_condition_same_reason", min(1.0, 0.35 + overlap)
    return None, 0.0


def name_overlap(source: CsmStateVariable, target: CsmStateVariable) -> float:
    source_terms = useful_terms(source)
    target_terms = useful_terms(target)
    if not source_terms or not target_terms:
        return 0.0
    return len(source_terms & target_terms) / max(1, min(len(source_terms), len(target_terms)))


def useful_terms(state: CsmStateVariable) -> set[str]:
    value = state.current_value or {}
    text = f"{state.state_key} {value.get('value')} {value.get('structured')}"
    stop = {"active", "condition", "medication", "allergy", "measurement", "status", "clinical", "none", "true", "false"}
    return {term for term in tokenize(text) if len(term) > 2 and term not in stop}


def risk_level_for_text(text: str) -> str:
    high_risk = {"allergy", "allergic", "anaphylaxis", "medication", "diagnosis", "treatment", "urgent", "discontinue", "stop"}
    return "high" if tokenize(text) & high_risk else "medium"


def is_correction_evidence(evidence: CsmEvidence) -> bool:
    return bool(tokenize(f"{evidence.content} {evidence.structured_value}") & {"corrected", "correction", "amended", "retracted", "retraction", "revised", "superseded"})


def selection_key(candidate: dict) -> str:
    state = candidate.get("state")
    evidence = candidate.get("evidence")
    if state is not None:
        suffix = "history" if candidate.get("historical") else "current"
        return f"state:{state.id}:{suffix}"
    if evidence is not None:
        return f"evidence:{evidence.canonical_source_id}:{evidence.evidence_type}"
    return candidate.get("content", "")
