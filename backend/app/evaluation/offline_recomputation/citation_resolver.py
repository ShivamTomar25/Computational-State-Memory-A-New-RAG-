from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.evaluation.offline_recomputation.scope_loader import OfflineTurn


@dataclass(frozen=True)
class CitationResolution:
    raw_id: str
    resolved_id: str | None
    classification: str
    calculation_reason: str


def resolve_turn_citations(turn: OfflineTurn, csm_aliases: dict[str, str] | None = None) -> list[CitationResolution]:
    valid_ids, aliases = citation_map(turn)
    if csm_aliases:
        aliases.update(csm_aliases)
        valid_ids.update(csm_aliases.values())
    return [
        resolve_citation_id(
            citation,
            answer_citations=turn.output.citations or [],
            valid_context_ids=valid_ids,
            aliases=aliases,
        )
        for citation in all_citation_ids(turn)
    ]


def resolve_citation_id(
    citation_id: str,
    *,
    answer_citations: list[Any] | tuple[Any, ...] | None,
    valid_context_ids: set[str] | list[str] | tuple[str, ...],
    aliases: dict[str, str] | None = None,
) -> CitationResolution:
    """Resolve a presentation citation ID into the canonical context ID expected by metrics.

    CSM v3 answers can cite local presentation aliases such as C1/C2 while storing the
    actual canonical source ID in the answer citation payload. Baseline systems also
    use direct UUID/document citations. This resolver supports both without changing
    metric semantics.
    """
    raw = str(citation_id)
    valid = {str(value) for value in valid_context_ids if value}
    alias_map = dict(aliases or {})

    for index, citation in enumerate(answer_citations or [], start=1):
        if isinstance(citation, dict):
            primary = citation.get("canonical_source_id") or citation.get("source_id") or citation.get("document_id") or citation.get("section_id")
            local = citation.get("citation_id") or citation.get("id") or f"C{index}"
            if primary:
                primary_text = str(primary)
                valid.add(primary_text)
                alias_map[str(local)] = primary_text
        elif citation:
            alias_map.setdefault(f"C{index}", str(citation))
            valid.add(str(citation))

    target = alias_map.get(raw, raw)
    if target in valid:
        return CitationResolution(raw, target, "valid_supporting", "resolved_through_turn_citation_map_or_retrieval_context")
    if raw.lower().startswith("state"):
        return CitationResolution(raw, None, "unresolved_internal_reference", "state_alias_not_linked_to_csm_evidence")
    if raw.startswith("C") and raw[1:].isdigit():
        return CitationResolution(raw, None, "not_in_supplied_context", "local_citation_alias_missing_from_turn_context")
    return CitationResolution(raw, None, "fabricated", "citation_not_resolvable_to_context_or_csm_lineage")


def citation_map(turn: OfflineTurn) -> tuple[set[str], dict[str, str]]:
    valid = set()
    aliases = {}
    for item in turn.retrieval_items:
        item_ids = [str(value) for value in (item.canonical_source_id, item.document_id, item.section_id, item.system_native_id) if value]
        if not item_ids:
            continue
        primary = item_ids[0]
        valid.update(item_ids)
        for alias in (f"C{item.rank}", f"c{item.rank}", str(item.rank), f"source_{item.rank}", f"rank_{item.rank}"):
            aliases[alias] = primary
    for index, citation in enumerate(turn.output.citations or [], start=1):
        if isinstance(citation, dict):
            primary = citation.get("canonical_source_id") or citation.get("source_id") or citation.get("document_id") or citation.get("section_id")
            local = citation.get("citation_id") or citation.get("id") or f"C{index}"
            if primary:
                valid.add(str(primary))
                aliases[str(local)] = str(primary)
        elif citation:
            aliases.setdefault(f"C{index}", str(citation))
    return valid, aliases


def all_citation_ids(turn: OfflineTurn) -> list[str]:
    ids = []
    for citation in turn.output.citations or []:
        if isinstance(citation, dict):
            for key in ("citation_id", "id", "source_id", "canonical_source_id", "document_id", "section_id"):
                if citation.get(key):
                    ids.append(str(citation[key]))
                    break
        elif citation:
            ids.append(str(citation))
    for claim in turn.claims:
        for citation in claim.citation_ids or []:
            if isinstance(citation, dict):
                value = citation.get("citation_id") or citation.get("source_id") or citation.get("canonical_source_id")
                if value:
                    ids.append(str(value))
            elif citation:
                ids.append(str(citation))
    return list(dict.fromkeys(ids))
