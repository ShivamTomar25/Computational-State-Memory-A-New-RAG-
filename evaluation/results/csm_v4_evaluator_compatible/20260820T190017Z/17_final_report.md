# CSM v4 Evaluator-Compatible Offline Report

## Validation

- New LLM calls during export: `0`
- Stored answers modified by export: `NO`
- Ground truth modified by export: `NO`
- Baseline values changed: `NO`
- CSM v4 completed turns: `60`
- Output directory: `/Users/shivamtomar/Desktop/Project - 1/sustha/evaluation/results/csm_v4_evaluator_compatible/20260820T190017Z`

## Code Files Changed

- `backend/app/memory_systems/csm/v4_engine.py`
- `backend/app/memory_systems/csm/v4_adapter.py`
- `backend/app/config.py`
- `backend/app/memory_systems/common/enums/status.py`
- `backend/app/memory_systems/common/registry/registry.py`
- `backend/app/memory_systems/common/services/memory_service.py`
- `backend/app/memory_systems/common/canonical/source_collector.py`
- `backend/app/evaluation/experiments/services/live_runner.py`
- `backend/app/evaluation/offline_recomputation/scope_loader.py`
- `backend/app/evaluation/offline_recomputation/statistics.py`
- `backend/app/evaluation/offline_recomputation/observation_builder.py`
- `backend/app/evaluation/offline_recomputation/metric_calculator.py`
- `backend/app/evaluation/scripts/diagnose_csm_v2_vs_v3_questions.py`
- `backend/app/evaluation/scripts/preflight_csm_v4_offline_gates.py`
- `backend/app/evaluation/scripts/export_csm_v4_evaluator_compatible.py`
- `backend/tests/memory_systems/test_csm_v4_engine.py`
- `backend/tests/memory_systems/test_memory_registry.py`

## Test Results

backend unittest discovery: 110 tests OK; csm_v4 exporter py_compile OK

## New Result Files

- `08_patient_1_v2_v3_v4_matrix.csv`
- `09_patient_2_v2_v3_v4_matrix.csv`
- `10_patient_3_v2_v3_v4_matrix.csv`
- `11_overall_pooled_matrix.csv`
- `12_overall_macro_matrix.csv`
- `13_csm_v2_v3_v4_comparison.csv`
- `14_all_system_rankings.csv`
- `15_statistical_comparisons.csv`

## CSM v4 Pooled Matrix

| Category | Metric | CSM v4 | N | Rank |
| --- | --- | --- | --- | --- |
| STATE | state_accuracy | 0.00000000 | 12 | 2 |
| TEMPORAL | temporal_consistency | 0.46969697 | 22 | 7 |
| QUALITY | decision_f1 | 0.00000000 | 3 | 1 |
| QUALITY | answer_accuracy | 0.16799182 | 60 | 4 |
| GROUNDING | hallucination_rate | 0.03333333 | 60 | 5 |
| GROUNDING | evidence_support_rate | 0.60944444 | 60 | 4 |
| GROUNDING | unsupported_claim_rate | 0.03333333 | 60 | 5 |
| GROUNDING | fabricated_citation_rate | 0.00000000 | 59 | 1 |
| GROUNDING | faithfulness | 0.60944444 | 60 | 4 |
| GROUNDING | groundedness | 0.60944444 | 60 | 4 |
| QUALITY | expected_calibration_error | 0.14386950 | 53 | 7 |
| GROUNDING | lineage_citation_f1 | 0.22939833 | 59 | 5 |
| QUALITY | contradiction_handling | 0.00000000 | 1 | 1 |
| TEMPORAL | correction_recovery | 0.32608696 | 23 | 7 |
| RETRIEVAL | retrieval_precision | 0.10121338 | 60 | 6 |
| RETRIEVAL | retrieval_recall | 0.24624519 | 60 | 5 |
| RETRIEVAL | activation_precision | 0.10121338 | 60 | 1 |
| RETRIEVAL | activation_recall | 0.24624519 | 60 | 1 |
| EFFICIENCY | tokens_per_query | 3626.46666667 | 60 | 9 |
| EFFICIENCY | p95_latency | 185454.00000000 | 60 | 9 |
| EFFICIENCY | provider_generation_latency_ms | 114549.25000000 | 60 | 8 |
| EFFICIENCY | retrieval_activation_latency_ms | 35.48333333 | 60 | 8 |
| EFFICIENCY | processing_latency_ms | 114549.25000000 | 60 | 8 |
| EFFICIENCY | operational_wall_clock_latency_ms | 114584.73333333 | 60 | 8 |
| COST | online_query_cost | 0.00072368 | 60 | 9 |
| COST | offline_csm_update_cost | 0.00000000 | 60 | 1 |
| COST | total_cost | 0.04342065 | 60 | 9 |
| STATE | memory_update_accuracy | 0.46666667 | 12 | 2 |
| STATE | state_recovery_time | 1.00000000 | 16 | 1 |

## CSM v2 vs CSM v3 vs CSM v4

| Category | Metric | CSM v2 | CSM v3 | CSM v4 | Best Baseline | V4 Rank | V4 vs V2 | V4 vs V3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| STATE | state_accuracy | 0.04166667 | 0.00000000 | 0.00000000 | NULL | 2 | regressed | unchanged |
| TEMPORAL | temporal_consistency | 0.50000000 | 0.48484848 | 0.46969697 | rolling_summary | 7 | regressed | regressed |
| QUALITY | decision_f1 | 0.00000000 | 0.00000000 | 0.00000000 | long_context | 1 | unchanged | unchanged |
| QUALITY | answer_accuracy | 0.13925067 | 0.10545635 | 0.16799182 | graph_rag | 4 | improved | improved |
| GROUNDING | hallucination_rate | 0.05084746 | 0.11607143 | 0.03333333 | graph_rag | 5 | improved | improved |
| GROUNDING | evidence_support_rate | 0.56436642 | 0.50446429 | 0.60944444 | graph_rag | 4 | improved | improved |
| GROUNDING | unsupported_claim_rate | 0.05084746 | 0.11607143 | 0.03333333 | graph_rag | 5 | improved | improved |
| GROUNDING | fabricated_citation_rate | 0.00000000 | 0.00666667 | 0.00000000 | long_context | 1 | unchanged | improved |
| GROUNDING | faithfulness | 0.56436642 | 0.50446429 | 0.60944444 | graph_rag | 4 | improved | improved |
| GROUNDING | groundedness | 0.56436642 | 0.50446429 | 0.60944444 | graph_rag | 4 | improved | improved |
| QUALITY | expected_calibration_error | 0.09862698 | 0.13894558 | 0.14386950 | rolling_summary | 7 | regressed | regressed |
| GROUNDING | lineage_citation_f1 | 0.14090164 | 0.07712915 | 0.22939833 | hybrid_rag | 5 | improved | improved |
| QUALITY | contradiction_handling | 0.00000000 | 0.00000000 | 0.00000000 | long_context | 1 | unchanged | unchanged |
| TEMPORAL | correction_recovery | 0.39130435 | 0.28260870 | 0.32608696 | rolling_summary | 7 | regressed | improved |
| RETRIEVAL | retrieval_precision | 0.06761905 | 0.04544372 | 0.10121338 | hybrid_rag | 6 | improved | improved |
| RETRIEVAL | retrieval_recall | 0.16966661 | 0.06412037 | 0.24624519 | hybrid_rag | 5 | improved | improved |
| RETRIEVAL | activation_precision | 0.06761905 | 0.04544372 | 0.10121338 | NULL | 1 | improved | improved |
| RETRIEVAL | activation_recall | 0.16966661 | 0.06412037 | 0.24624519 | NULL | 1 | improved | improved |
| EFFICIENCY | tokens_per_query | 3086.76666667 | 2622.31666667 | 3626.46666667 | long_context | 9 | regressed | regressed |
| EFFICIENCY | p95_latency | 128117.00000000 | 68848.00000000 | 185454.00000000 | long_context | 9 | regressed | regressed |
| EFFICIENCY | provider_generation_latency_ms | 100779.01666667 | 37025.21666667 | 114549.25000000 | long_context | 8 | regressed | regressed |
| EFFICIENCY | retrieval_activation_latency_ms | 37.81666667 | 29.26666667 | 35.48333333 | graph_rag | 8 | improved | regressed |
| EFFICIENCY | processing_latency_ms | 100779.01666667 | 37025.21666667 | 114549.25000000 | long_context | 8 | regressed | regressed |
| EFFICIENCY | operational_wall_clock_latency_ms | 100816.83333333 | 37054.48333333 | 114584.73333333 | long_context | 8 | regressed | regressed |
| COST | online_query_cost | 0.00063987 | 0.00056368 | 0.00072368 | long_context | 9 | regressed | regressed |
| COST | offline_csm_update_cost | 0.00000000 | 0.00000000 | 0.00000000 | NULL | 1 | unchanged | unchanged |
| COST | total_cost | 0.03839190 | 0.03382080 | 0.04342065 | long_context | 9 | regressed | regressed |
| STATE | memory_update_accuracy | 0.25833333 | 0.17500000 | 0.46666667 | hippo_rag | 2 | improved | improved |
| STATE | state_recovery_time | 1.00000000 | 1.00000000 | 1.00000000 | NULL | 1 | unchanged | unchanged |

Statistical comparison rows: `232`.
