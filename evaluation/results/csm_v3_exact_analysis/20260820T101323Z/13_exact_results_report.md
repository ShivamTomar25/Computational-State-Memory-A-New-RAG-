# Exact CSM v2/v3 Research Matrix Report

## RUN VALIDATION

Patients: 3

Questions: 60

Systems in final comparison: 8

CSM v3 completed turns: 60

New LLM calls: 0

## Canonical Sources

- Baseline/CSM v2 exact values use finalized offline `metric_observations.csv` and `system_metric_matrix.csv` under `evaluation/results/csm_v2_final_comparison_offline_v3/...`.
- CSM v3 exact patient values use stored DB `evaluation_metric_results` for experiment `2327c728-69ec-4fc4-9410-771c225d61a0` plus exported `token_results.csv` for pooled latency/cost/token observations.
- Baseline/v2 P2/P3 legacy raw patient-column issue is handled by `scope_validation.json` and `BenchmarkCase.case_key`, not stale matrix labels.

## EXACT OVERALL MATRIX

| Metric | Long Context | Rolling Summary | Dense RAG | Hybrid RAG | GraphRAG | HippoRAG | CSM v2 | CSM v3 | CSM v3 Rank |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| state_accuracy | NULL | NULL | NULL | NULL | NULL | NULL | 0.04166667 | 0.00000000 | 2 |
| temporal_consistency | 0.43939394 | 0.56060606 | 0.53030303 | 0.46969697 | 0.51515152 | 0.42424242 | 0.50000000 | NULL | NULL |
| decision_f1 | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | NULL | NULL |
| answer_accuracy | 0.12628205 | 0.10448343 | 0.17560533 | 0.16935622 | 0.18699532 | 0.15836696 | 0.13925067 | 0.00000000 | 8 |
| hallucination_rate | 0.23717949 | 0.00350877 | 0.04519774 | 0.02259887 | 0.00277778 | 0.00282486 | 0.05084746 | 1.00000000 | 8 |
| evidence_support_rate | 0.47716346 | 0.57273392 | 0.59901130 | 0.61440678 | 0.64402778 | 0.62040960 | 0.56436642 | 0.00000000 | 8 |
| unsupported_claim_rate | 0.23717949 | 0.00350877 | 0.04519774 | 0.02259887 | 0.00277778 | 0.00282486 | 0.05084746 | 1.00000000 | 8 |
| fabricated_citation_rate | 0.00000000 | 0.00000000 | 0.00308166 | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | 0.47142857 | 8 |
| faithfulness | 0.47716346 | 0.57273392 | 0.59901130 | 0.61440678 | 0.64402778 | 0.62040960 | 0.56436642 | 0.89166667 | 1 |
| groundedness | 0.47716346 | 0.57273392 | 0.59901130 | 0.61440678 | 0.64402778 | 0.62040960 | 0.56436642 | 0.89166667 | 1 |
| expected_calibration_error | 0.17732143 | 0.07150327 | 0.17696226 | 0.12595425 | 0.08838724 | 0.09819444 | 0.09862698 | 0.89181818 | 8 |
| lineage_citation_f1 | 0.09091871 | 0.12758053 | 0.29176715 | 0.35670461 | 0.34656868 | 0.35028556 | 0.14090164 | 0.29629630 | 4 |
| contradiction_handling | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | 0.00000000 | 1 |
| correction_recovery | 0.11956522 | 0.44565217 | 0.36956522 | 0.36956522 | 0.43478261 | 0.36956522 | 0.39130435 | 0.00000000 | 8 |
| retrieval_precision | 0.02916667 | 0.13316498 | 0.17227129 | 0.17329899 | 0.16630020 | 0.17152838 | 0.06761905 | 0.38333333 | 1 |
| retrieval_recall | 0.04875000 | 0.20482781 | 0.38814336 | 0.45015466 | 0.41999984 | 0.44038963 | 0.16966661 | 0.60526316 | 1 |
| activation_precision | NULL | NULL | NULL | NULL | NULL | NULL | 0.06761905 | NULL | NULL |
| activation_recall | NULL | NULL | NULL | NULL | NULL | NULL | 0.16966661 | NULL | NULL |
| tokens_per_query | 1579.28333333 | 2684.60000000 | 2059.11666667 | 2217.18333333 | 2221.78333333 | 2199.53333333 | 3086.76666667 | 2622.31666667 | 6 |
| p95_latency | 42706.00000000 | 129182.00000000 | 126237.00000000 | 127982.00000000 | 128680.00000000 | 128597.00000000 | 128117.00000000 | 68853.25000000 | 2 |
| total_cost | 0.02301375 | 0.03636135 | 0.03038370 | 0.03145980 | 0.03148635 | 0.03198585 | 0.03839190 | 0.03382080 | 6 |
| memory_update_accuracy | 0.20833333 | 0.17500000 | 0.21666667 | 0.30000000 | 0.34166667 | 0.55000000 | 0.25833333 | NULL | NULL |
| state_recovery_time | NULL | NULL | NULL | NULL | NULL | NULL | 1.00000000 | NULL | NULL |
| offline_csm_update_cost | NULL | NULL | NULL | NULL | NULL | NULL | 0.00000000 | NULL | NULL |
| online_query_cost | 0.00038356 | 0.00060602 | 0.00050640 | 0.00052433 | 0.00052477 | 0.00053310 | 0.00063987 | NULL | NULL |
| operational_wall_clock_latency_ms | 24351.55000000 | 65760.08333333 | 59106.76666667 | 71803.75000000 | 116032.50000000 | 110972.95000000 | 100816.83333333 | NULL | NULL |
| processing_latency_ms | 24343.30000000 | 65749.95000000 | 59073.71666667 | 71770.48333333 | 116024.86666667 | 110948.13333333 | 100779.01666667 | NULL | NULL |
| provider_generation_latency_ms | 24343.30000000 | 65749.95000000 | 59073.71666667 | 71770.48333333 | 116024.86666667 | 110948.13333333 | 100779.01666667 | NULL | NULL |
| retrieval_activation_latency_ms | 8.25000000 | 10.13333333 | 33.05000000 | 33.26666667 | 7.63333333 | 24.81666667 | 37.81666667 | NULL | NULL |

## CSM V2 -> V3

| Metric | v2 | v3 | difference | % change | verdict |
| --- | --- | --- | --- | --- | --- |
| state_accuracy | 0.04166667 | 0.00000000 | -0.04166667 | -100.00000000 | regressed |
| temporal_consistency | 0.50000000 | NULL | NULL | NULL | not_comparable |
| decision_f1 | 0.00000000 | NULL | NULL | NULL | not_comparable |
| answer_accuracy | 0.13925067 | 0.00000000 | -0.13925067 | -100.00000000 | regressed |
| hallucination_rate | 0.05084746 | 1.00000000 | 0.94915254 | 1866.66666667 | regressed |
| evidence_support_rate | 0.56436642 | 0.00000000 | -0.56436642 | -100.00000000 | regressed |
| unsupported_claim_rate | 0.05084746 | 1.00000000 | 0.94915254 | 1866.66666667 | regressed |
| fabricated_citation_rate | 0.00000000 | 0.47142857 | 0.47142857 | NULL | regressed |
| faithfulness | 0.56436642 | 0.89166667 | 0.32730024 | 57.99427959 | improved |
| groundedness | 0.56436642 | 0.89166667 | 0.32730024 | 57.99427959 | improved |
| expected_calibration_error | 0.09862698 | 0.89181818 | 0.79319120 | 804.23345062 | regressed |
| lineage_citation_f1 | 0.14090164 | 0.29629630 | 0.15539465 | 110.28590699 | improved |
| contradiction_handling | 0.00000000 | 0.00000000 | 0.00000000 | NULL | unchanged |
| correction_recovery | 0.39130435 | 0.00000000 | -0.39130435 | -100.00000000 | regressed |
| retrieval_precision | 0.06761905 | 0.38333333 | 0.31571429 | 466.90140845 | improved |
| retrieval_recall | 0.16966661 | 0.60526316 | 0.43559655 | 256.73676172 | improved |
| activation_precision | 0.06761905 | NULL | NULL | NULL | not_comparable |
| activation_recall | 0.16966661 | NULL | NULL | NULL | not_comparable |
| tokens_per_query | 3086.76666667 | 2622.31666667 | -464.45000000 | -15.04648877 | improved |
| p95_latency | 128117.00000000 | 68853.25000000 | -59263.75000000 | -46.25752242 | improved |
| total_cost | 0.03839190 | 0.03382080 | -0.00457110 | -11.90641776 | improved |
| memory_update_accuracy | 0.25833333 | NULL | NULL | NULL | not_comparable |
| state_recovery_time | 1.00000000 | NULL | NULL | NULL | not_comparable |
| offline_csm_update_cost | 0.00000000 | NULL | NULL | NULL | not_comparable |
| online_query_cost | 0.00063987 | NULL | NULL | NULL | not_comparable |
| operational_wall_clock_latency_ms | 100816.83333333 | NULL | NULL | NULL | not_comparable |
| processing_latency_ms | 100779.01666667 | NULL | NULL | NULL | not_comparable |
| provider_generation_latency_ms | 100779.01666667 | NULL | NULL | NULL | not_comparable |
| retrieval_activation_latency_ms | 37.81666667 | NULL | NULL | NULL | not_comparable |

## IMPORTANT DIAGNOSIS

The suspicious CSM v3 values are stored measured CSM v3 metric outputs, but the direct evidence indicates evaluator/output-schema/citation-resolution incompatibility rather than no retrieved support in the answers.

- `answer_accuracy = 0`: live matcher stored `true_positive = 0` for every CSM v3 patient.
- `hallucination_rate = 1`: live classifier counted every generated claim as unsupported because `source_support_status` was blank and no normalized ground-truth matches were found.
- `evidence_support_rate = 0`: same mechanism; supported claim count is zero in stored metric details.
- `faithfulness` and `groundedness` are high because generated claims cite supplied context IDs; this is a different evaluator path than answer accuracy/support classification.
- `fabricated_citation_rate` is inflated by C-style aliases. Exported citations have `citation_id=C1/C2/...` and also have `canonical_source_id`, but the live metric compares normalized citation IDs to valid context IDs without resolving the alias to canonical source ID.

See `12_csm_v3_anomaly_diagnosis.md`, `10_citation_resolution_audit.csv`, and `11_metric_applicability_audit.csv` for direct evidence.
