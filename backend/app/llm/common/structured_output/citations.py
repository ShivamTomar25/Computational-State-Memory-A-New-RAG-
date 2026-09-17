from __future__ import annotations

from app.llm.common.schemas.answer import GroundedAnswer, LlmContextBlock, ValidatedAnswerResult


def validate_answer_citations(answer: GroundedAnswer, context: list[LlmContextBlock]) -> ValidatedAnswerResult:
    allowed = {item.citation_id for item in context}
    valid_citations = []
    invalid = []

    for citation in answer.citations:
        if citation.citation_id in allowed:
            valid_citations.append(citation)
        else:
            invalid.append(citation.citation_id)

    return ValidatedAnswerResult(
        answer=answer.model_copy(update={"citations": valid_citations}),
        invalid_citation_ids=invalid,
    )
