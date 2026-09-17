from __future__ import annotations

from app.evaluation.offline_recomputation.claim_matcher import normalize_clinical_text, semantic_score
from app.evaluation.offline_recomputation.scope_loader import CsmBundle


def expected_state_strings(truth) -> list[str]:
    payload = getattr(truth, "truth", None) or {}
    expected = []
    state = payload.get("expected_state") or {}
    if isinstance(state, dict):
        expected.extend(f"{key} {value}" for key, value in state.items())
    expected.extend(str(item) for item in payload.get("expected_state_transitions") or [])
    return expected


def csm_state_accuracy(bundle: CsmBundle, truth) -> tuple[float | None, str, dict]:
    expected = expected_state_strings(truth)
    if not expected:
        return None, "missing_expected_state", {}
    state_texts = [
        normalize_clinical_text(f"{state.state_type} {state.state_key} {state.current_value} {state.status}")
        for state in bundle.states
    ]
    if not state_texts:
        return None, "missing_csm_state_records", {"expected": expected}
    matched = 0
    for expected_item in expected:
        if max((semantic_score(expected_item, state_text) for state_text in state_texts), default=0.0) >= 0.56:
            matched += 1
    return matched / len(expected), "matched_expected_state_against_real_csm_state_table", {"matched": matched, "expected": len(expected)}


def memory_update_accuracy(answer: str, truth) -> tuple[float | None, str]:
    expected = expected_state_strings(truth)
    if not expected:
        return None, "missing_expected_state_transitions"
    matched = sum(1 for item in expected if semantic_score(answer, item) >= 0.40)
    return matched / len(expected), "expected_state_transition_terms_found_in_stored_answer"

