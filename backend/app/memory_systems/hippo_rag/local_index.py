from __future__ import annotations

from app.memory_systems.graph_rag.local_index import extract_entities, lexical_score, tokenize


def passage_score(*, query: str, passage: str, passage_entities: list[str]) -> tuple[float, list[str]]:
    query_entities = {entity["normalized_name"] for entity in extract_entities(query, limit=12)}
    passage_entity_set = set(passage_entities)
    matched_entities = sorted(query_entities & passage_entity_set)
    entity_score = len(matched_entities) / max(1, len(query_entities))
    term_score = lexical_score(query, passage)
    propagation_score = related_term_score(query=query, passage_entities=passage_entity_set)

    return (entity_score * 2.0) + term_score + propagation_score, matched_entities


def related_term_score(*, query: str, passage_entities: set[str]) -> float:
    query_terms = set(tokenize(query))

    if not query_terms or not passage_entities:
        return 0

    related = 0

    for term in query_terms:
        if any(term in entity or entity in term for entity in passage_entities):
            related += 1

    return related / len(query_terms)
