# CSM v4 Offline Gate Summary

Status: **passed**

Patients: 1
Questions: 1
Provider calls: 0
Groq calls: 0

## Gates

| Gate | Passed | Measure | Value |
| --- | --- | --- | --- |
| no_future_leakage | True | future_leak_count | 0 |
| correction_bundle_works | True | correction_questions | 0 |
| current_state_excludes_superseded | True | current_route_questions | 1 |
| temporal_retrieves_history_or_v2_coverage | True | temporal_questions | 0 |
| exact_source_fallback_works | True | exact_source_questions | 0 |
| rare_detail_fallback_works | True | rare_detail_questions | 0 |
| state_evidence_lineage_deterministic | True | state_without_evidence/null_canonical | "0/0" |
| adaptive_context_budget_works | True | max_token_count | 1114 |
| retrieval_coverage_not_worse_than_csm_v2 | True | macro_recall_v4_vs_v2 | {"v4": 0.5, "v2": 0.4, "delta": 0.09999999999999998} |
| csm_v2_v3_unchanged_static_check | True | versions | {"csm_v2": "csm_v2", "csm_v3": "csm_v3"} |

## Retrieval Coverage

| Patient | Q | Route | v2 recall | v4 recall | v4 precision | Tokens |
| --- | --- | --- | --- | --- | --- | --- |
| SYN-CSM-001 | 1 | state_first | 0.4000 | 0.5000 | 0.4000 | 1114 |
