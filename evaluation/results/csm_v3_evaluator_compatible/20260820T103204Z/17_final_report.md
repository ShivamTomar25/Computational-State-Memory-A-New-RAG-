# CSM v3 Evaluator-Compatible Offline Report

## Validation

- New LLM calls: `0`
- Stored CSM v3 answers modified: `NO`
- Ground truth modified: `NO`
- Baseline values changed: `NO`
- Output directory: `/Users/shivamtomar/Desktop/Project - 1/sustha/evaluation/results/csm_v3_evaluator_compatible/20260820T103204Z`

## Code Files Changed

- `backend/app/evaluation/offline_recomputation/citation_resolver.py`
- `backend/app/evaluation/offline_recomputation/metric_calculator.py`
- `backend/app/evaluation/offline_recomputation/exporter.py`
- `backend/app/evaluation/scripts/export_csm_v3_evaluator_compatible.py`
- `backend/tests/evaluation/test_csm_v3_evaluator_compatibility.py`

## Test Results

Syntax check: py_compile passed for compatibility modules and exporter. Targeted tests: python -m unittest tests.evaluation.test_csm_v3_evaluator_compatibility -> 8 tests OK. Full backend tests: python -m unittest discover -s tests -p test_*.py -> 97 tests OK.

## New Result Files

- `08_patient_1_recomputed_matrix.csv`
- `09_patient_2_recomputed_matrix.csv`
- `10_patient_3_recomputed_matrix.csv`
- `11_overall_pooled_matrix.csv`
- `12_overall_macro_matrix.csv`
- `13_csm_v2_vs_v3.csv`
- `14_all_system_rankings.csv`
- `15_statistical_comparisons.csv`

## Compatibility Bugs Fixed

- CSM v3 presentation citations `C1`, `C2`, etc. are resolved to canonical source IDs before citation metrics.
- Blank CSM v3 `source_support_status` is no longer treated by the live aggregate path as the only support signal; offline support classification now uses the same deterministic matcher/citation semantics as the frozen v2 analysis.
- Activation, temporal, correction, state, and memory-update observations are exported at benchmark question level from the offline observation builder.

## CSM v3 Pooled Matrix

| Metric | CSM v3 | N | Rank |
| --- | --- | --- | --- |
| state_accuracy | 0.00000000 | 12 | 2 |
| temporal_consistency | 0.48484848 | 22 | 5 |
| decision_f1 | 0.00000000 | 3 | 1 |
| answer_accuracy | 0.10545635 | 56 | 7 |
| hallucination_rate | 0.11607143 | 56 | 7 |
| evidence_support_rate | 0.50446429 | 56 | 7 |
| unsupported_claim_rate | 0.11607143 | 56 | 7 |
| fabricated_citation_rate | 0.00666667 | 50 | 8 |
| faithfulness | 0.50446429 | 56 | 7 |
| groundedness | 0.50446429 | 56 | 7 |
| expected_calibration_error | 0.13894558 | 49 | 6 |
| lineage_citation_f1 | 0.07750549 | 50 | 8 |
| contradiction_handling | 0.00000000 | 1 | 1 |
| correction_recovery | 0.28260870 | 23 | 7 |
| retrieval_precision | 0.04544372 | 60 | 7 |
| retrieval_recall | 0.06428945 | 60 | 7 |
| activation_precision | 0.04544372 | 60 | 2 |
| activation_recall | 0.06428945 | 60 | 2 |
| tokens_per_query | 2622.31666667 | 60 | 6 |
| p95_latency | 68848.00000000 | 60 | 2 |
| provider_generation_latency_ms | 37025.21666667 | 60 | 2 |
| retrieval_activation_latency_ms | 29.26666667 | 60 | 5 |
| processing_latency_ms | 37025.21666667 | 60 | 2 |
| operational_wall_clock_latency_ms | 37054.48333333 | 60 | 2 |
| online_query_cost | 0.00056368 | 60 | 6 |
| offline_csm_update_cost | 0.00000000 | 60 | 1 |
| total_cost | 0.03382080 | 60 | 6 |
| memory_update_accuracy | 0.17500000 | 12 | 7 |
| state_recovery_time | 1.00000000 | 14 | 1 |

## CSM v2 vs CSM v3

| Metric | CSM v2 | CSM v3 | Difference | % Change | Verdict |
| --- | --- | --- | --- | --- | --- |
| state_accuracy | 0.04166667 | 0.00000000 | -0.04166667 | -100.00000000 | regressed |
| temporal_consistency | 0.50000000 | 0.48484848 | -0.01515152 | -3.03030303 | regressed |
| decision_f1 | 0.00000000 | 0.00000000 | 0.00000000 | NULL | unchanged |
| answer_accuracy | 0.13925067 | 0.10545635 | -0.03379432 | -24.26869477 | regressed |
| hallucination_rate | 0.05084746 | 0.11607143 | 0.06522397 | 128.27380952 | regressed |
| evidence_support_rate | 0.56436642 | 0.50446429 | -0.05990214 | -10.61405077 | regressed |
| unsupported_claim_rate | 0.05084746 | 0.11607143 | 0.06522397 | 128.27380952 | regressed |
| fabricated_citation_rate | 0.00000000 | 0.00666667 | 0.00666667 | NULL | regressed |
| faithfulness | 0.56436642 | 0.50446429 | -0.05990214 | -10.61405077 | regressed |
| groundedness | 0.56436642 | 0.50446429 | -0.05990214 | -10.61405077 | regressed |
| expected_calibration_error | 0.09862698 | 0.13894558 | 0.04031859 | 40.87988136 | regressed |
| lineage_citation_f1 | 0.14090164 | 0.07750549 | -0.06339615 | -44.99319292 | regressed |
| contradiction_handling | 0.00000000 | 0.00000000 | 0.00000000 | NULL | unchanged |
| correction_recovery | 0.39130435 | 0.28260870 | -0.10869565 | -27.77777778 | regressed |
| retrieval_precision | 0.06761905 | 0.04544372 | -0.02217532 | -32.79449424 | regressed |
| retrieval_recall | 0.16966661 | 0.06428945 | -0.10537715 | -62.10836428 | regressed |
| activation_precision | 0.06761905 | 0.04544372 | -0.02217532 | -32.79449424 | regressed |
| activation_recall | 0.16966661 | 0.06428945 | -0.10537715 | -62.10836428 | regressed |
| tokens_per_query | 3086.76666667 | 2622.31666667 | -464.45000000 | -15.04648877 | improved |
| p95_latency | 128117.00000000 | 68848.00000000 | -59269.00000000 | -46.26162024 | improved |
| provider_generation_latency_ms | 100779.01666667 | 37025.21666667 | -63753.80000000 | -63.26098637 | improved |
| retrieval_activation_latency_ms | 37.81666667 | 29.26666667 | -8.55000000 | -22.60907889 | improved |
| processing_latency_ms | 100779.01666667 | 37025.21666667 | -63753.80000000 | -63.26098637 | improved |
| operational_wall_clock_latency_ms | 100816.83333333 | 37054.48333333 | -63762.35000000 | -63.24573773 | improved |
| online_query_cost | 0.00063987 | 0.00056368 | -0.00007619 | -11.90641776 | improved |
| offline_csm_update_cost | 0.00000000 | 0.00000000 | 0.00000000 | NULL | unchanged |
| total_cost | 0.03839190 | 0.03382080 | -0.00457110 | -11.90641776 | improved |
| memory_update_accuracy | 0.25833333 | 0.17500000 | -0.08333333 | -32.25806452 | regressed |
| state_recovery_time | 1.00000000 | 1.00000000 | 0.00000000 | 0.00000000 | unchanged |

## Non-Applicable CSM v3 Metrics

| Metric | N |
| --- | --- |

Statistical comparison rows: `203`.
