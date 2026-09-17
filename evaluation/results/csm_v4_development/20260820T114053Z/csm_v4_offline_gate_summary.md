# CSM v4 Offline Gate Summary

Status: **failed**

Patients: 3
Questions: 60
Provider calls: 0
Groq calls: 0

## Gates

| Gate | Passed | Measure | Value |
| --- | --- | --- | --- |
| no_future_leakage | True | future_leak_count | 0 |
| correction_bundle_works | True | correction_questions | 8 |
| current_state_excludes_superseded | True | current_route_questions | 31 |
| temporal_retrieves_history_or_v2_coverage | False | temporal_questions | 21 |
| exact_source_fallback_works | True | exact_source_questions | 9 |
| rare_detail_fallback_works | True | rare_detail_questions | 0 |
| state_evidence_lineage_deterministic | True | state_without_evidence/null_canonical | "0/0" |
| adaptive_context_budget_works | True | max_token_count | 2400 |
| retrieval_coverage_not_worse_than_csm_v2 | True | macro_recall_v4_vs_v2 | {"v4": 0.3066964285714286, "v2": 0.16966660654160653, "delta": 0.13702982202982206} |
| csm_v2_v3_unchanged_static_check | True | versions | {"csm_v2": "csm_v2", "csm_v3": "csm_v3"} |

## Retrieval Coverage

| Patient | Q | Route | v2 recall | v4 recall | v4 precision | Tokens |
| --- | --- | --- | --- | --- | --- | --- |
| SYN-CSM-001 | 1 | state_first | 0.4000 | 0.5000 | 0.4000 | 1114 |
| SYN-CSM-001 | 2 | temporal_state | 0.4000 | 0.7500 | 0.3750 | 2249 |
| SYN-CSM-001 | 3 | temporal_state | 0.0000 | 0.0000 | 0.0000 | 2400 |
| SYN-CSM-001 | 4 | temporal_state | 0.2500 | 0.0000 | 0.0000 | 2254 |
| SYN-CSM-001 | 5 | temporal_state | 0.0000 | 0.2500 | 0.1250 | 2198 |
| SYN-CSM-001 | 6 | correction_state | 0.4000 | 0.5000 | 0.1667 | 2278 |
| SYN-CSM-001 | 7 | correction_state | 0.2000 | 0.0000 | 0.0000 | 2291 |
| SYN-CSM-001 | 8 | temporal_state | 0.0000 | 0.5000 | 0.2000 | 2258 |
| SYN-CSM-001 | 9 | temporal_state | 0.0000 | 0.0000 | 0.0000 | 2249 |
| SYN-CSM-001 | 10 | decision_state | 0.0000 | 0.0000 | 0.0000 | 1683 |
| SYN-CSM-001 | 11 | correction_state | 0.3333 | 0.5000 | 0.0909 | 2291 |
| SYN-CSM-001 | 12 | exact_source | 0.4286 | 0.5000 | 0.3750 | 1972 |
| SYN-CSM-001 | 13 | temporal_state | 0.0000 | 0.7500 | 0.2500 | 2326 |
| SYN-CSM-001 | 14 | high_risk_review | 0.0000 | 0.0000 | 0.0000 | 1840 |
| SYN-CSM-001 | 15 | exact_source | 0.4286 | 0.2857 | 0.2000 | 2000 |
| SYN-CSM-001 | 16 | correction_state | 0.3333 | 0.5000 | 0.0769 | 2300 |
| SYN-CSM-001 | 17 | state_first | 0.0000 | 0.0000 | 0.0000 | 1346 |
| SYN-CSM-001 | 18 | correction_state | 0.4444 | 0.2500 | 0.2000 | 2365 |
| SYN-CSM-001 | 19 | exact_source | 0.0000 | 0.5000 | 0.1250 | 1959 |
| SYN-CSM-001 | 20 | hybrid_state_evidence | 0.0000 | 0.0000 | 0.0000 | 2150 |
| SYN-CSM-002 | 1 | state_first | 0.5000 | 0.3333 | 0.2500 | 1149 |
| SYN-CSM-002 | 2 | temporal_state | 0.3333 | 0.6667 | 0.2500 | 2377 |
| SYN-CSM-002 | 3 | temporal_state | 0.2000 | 0.2500 | 0.1250 | 2394 |
| SYN-CSM-002 | 4 | high_risk_review | 0.0000 | 0.0000 | 0.0000 | 1149 |
| SYN-CSM-002 | 5 | high_risk_review | 0.0000 | 0.0000 | 0.0000 | 1149 |
| SYN-CSM-002 | 6 | state_first | 0.3333 | 0.5000 | 0.2000 | 1229 |
| SYN-CSM-002 | 7 | temporal_state | 0.0000 | 0.3333 | 0.2500 | 2360 |
| SYN-CSM-002 | 8 | high_risk_review | 0.0000 | 0.0000 | 0.0000 | 1149 |
| SYN-CSM-002 | 9 | state_first | 0.0000 | 0.0000 | 0.0000 | 1194 |
| SYN-CSM-002 | 10 | correction_state | 0.6667 | 1.0000 | 0.1667 | 2322 |
| SYN-CSM-002 | 11 | temporal_state | 0.1250 | 0.4286 | 0.4286 | 2292 |
| SYN-CSM-002 | 12 | exact_source | 0.0625 | 0.0625 | 0.1250 | 1897 |
| SYN-CSM-002 | 13 | temporal_state | 0.2500 | 0.3333 | 0.1429 | 2292 |
| SYN-CSM-002 | 14 | temporal_state | 0.0000 | 0.0000 | 0.0000 | 2333 |
| SYN-CSM-002 | 15 | temporal_state | 0.0909 | 0.2000 | 0.2857 | 2374 |
| SYN-CSM-002 | 16 | correction_state | 0.0000 | 0.6667 | 0.3333 | 2322 |
| SYN-CSM-002 | 17 | exact_source | 0.4000 | 0.4000 | 0.2222 | 1937 |
| SYN-CSM-002 | 18 | temporal_state | 0.0000 | 0.2500 | 0.2000 | 2379 |
| SYN-CSM-002 | 19 | state_first | 0.0000 | 0.0000 | 0.0000 | 1149 |
| SYN-CSM-002 | 20 | hybrid_state_evidence | 0.0000 | 0.1000 | 0.1250 | 1960 |
| SYN-CSM-003 | 1 | state_first | 0.5000 | 0.6000 | 0.6000 | 1141 |
| SYN-CSM-003 | 2 | state_first | 0.2500 | 0.3333 | 0.2000 | 1136 |
| SYN-CSM-003 | 3 | temporal_state | 0.0000 | 0.5000 | 0.2500 | 2281 |
| SYN-CSM-003 | 4 | temporal_state | 0.0000 | 0.5000 | 0.2222 | 2254 |
| SYN-CSM-003 | 5 | high_risk_review | 0.0000 | 0.0000 | 0.0000 | 1721 |
| SYN-CSM-003 | 6 | temporal_state | 0.2500 | 0.6667 | 0.2222 | 2259 |
| SYN-CSM-003 | 7 | exact_source | 0.2000 | 0.2500 | 0.1000 | 1999 |
| SYN-CSM-003 | 8 | correction_state | 0.2500 | 1.0000 | 0.2500 | 2364 |
| SYN-CSM-003 | 9 | temporal_state | 0.3333 | 1.0000 | 0.1818 | 2304 |
| SYN-CSM-003 | 10 | high_risk_review | 0.0000 | 0.0000 | 0.0000 | 1722 |
| SYN-CSM-003 | 11 | dependency_state | 0.0000 | 0.0000 | 0.0000 | 2175 |
| SYN-CSM-003 | 12 | high_risk_review | 0.0000 | 0.0000 | 0.0000 | 1722 |
| SYN-CSM-003 | 13 | exact_source | 0.3333 | 0.5000 | 0.1000 | 1999 |
| SYN-CSM-003 | 14 | temporal_state | 0.0000 | 0.5000 | 0.1818 | 2304 |
| SYN-CSM-003 | 15 | temporal_state | 0.0000 | 0.0000 | 0.0000 | 2259 |
| SYN-CSM-003 | 16 | high_risk_review | 0.0000 | 0.0000 | 0.0000 | 1722 |
| SYN-CSM-003 | 17 | exact_source | 0.7500 | 0.6667 | 0.2000 | 1999 |
| SYN-CSM-003 | 18 | exact_source | 0.4000 | 0.2000 | 0.1000 | 2000 |
| SYN-CSM-003 | 19 | evidence_first | 0.3333 | 0.3750 | 0.2727 | 1998 |
| SYN-CSM-003 | 20 | hybrid_state_evidence | 0.0000 | 0.0000 | 0.0000 | 2013 |
