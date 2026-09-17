from __future__ import annotations

from app.evaluation.claims.normalization.normalizer import claim_key
from app.evaluation.claims.schemas.claim import ClaimMatch, NormalizedClaim


MATCH_THRESHOLD = 0.72


def match_claims(generated_claims: list[NormalizedClaim], truth_claims: list[NormalizedClaim]) -> list[ClaimMatch]:
    unused_truth = list(truth_claims)
    matches = []

    for generated in generated_claims:
        best_truth = None
        best_score = 0.0

        for truth in unused_truth:
            score = match_score(generated, truth)

            if score > best_score:
                best_truth = truth
                best_score = score

        if best_truth is not None and best_score >= MATCH_THRESHOLD:
            unused_truth.remove(best_truth)
            matches.append(ClaimMatch(generated, best_truth, best_score, True, "structured_claim_match"))
        else:
            matches.append(ClaimMatch(generated, best_truth, best_score, False, "no_ground_truth_match"))

    return matches


def match_score(generated: NormalizedClaim, truth: NormalizedClaim) -> float:
    if claim_key(generated) == claim_key(truth):
        return 1.0

    components = [
        _field_score(generated.subject, truth.subject, 0.30),
        _field_score(generated.predicate, truth.predicate, 0.20),
        _field_score(generated.value, truth.value, 0.30),
        _field_score(generated.status, truth.status, 0.10),
        0.10 if generated.negation == truth.negation else 0.0,
    ]
    return sum(components)


def _field_score(generated: str, truth: str, weight: float) -> float:
    if not generated and not truth:
        return weight

    if not generated or not truth:
        return 0.0

    if generated == truth:
        return weight

    generated_tokens = set(generated.split())
    truth_tokens = set(truth.split())

    if not generated_tokens or not truth_tokens:
        return 0.0

    overlap = len(generated_tokens & truth_tokens) / len(generated_tokens | truth_tokens)
    return weight * overlap
