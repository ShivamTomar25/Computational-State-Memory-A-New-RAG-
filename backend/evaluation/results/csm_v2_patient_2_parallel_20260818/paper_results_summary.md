# Sustha Three-Patient Pilot Results

This is a synthetic pilot/integration benchmark. It should not be interpreted as evidence of broad clinical generalization.

Experiment status: `completed`.
Completed turns: `140` of `140`.
Measured metric rows: `119`.

## Top Systems By Metric
- `state_accuracy`: long_context (0), rolling_summary (0), dense_rag (0).
- `temporal_consistency`: no measured systems.
- `decision_f1`: no measured systems.
- `answer_accuracy`: long_context (0), rolling_summary (0), dense_rag (0).
- `hallucination_rate`: long_context (1), rolling_summary (1), dense_rag (1).
- `evidence_support_rate`: long_context (0), rolling_summary (0), dense_rag (0).
- `unsupported_claim_rate`: long_context (1), rolling_summary (1), dense_rag (1).
- `fabricated_citation_rate`: hybrid_rag (0.2424), hippo_rag (0.2667), graph_rag (0.2759).
- `faithfulness`: graph_rag (1), hippo_rag (1), rolling_summary (0.9714).
- `groundedness`: graph_rag (1), hippo_rag (1), rolling_summary (0.9714).
- `expected_calibration_error`: hybrid_rag (0.8302), dense_rag (0.8359), long_context (0.8979).
- `lineage_citation_f1`: dense_rag (0.3111), hybrid_rag (0.2857), long_context (0.2105).
- `contradiction_handling`: long_context (0), rolling_summary (0), dense_rag (0).
- `correction_recovery`: long_context (0), rolling_summary (0), dense_rag (0).
- `retrieval_precision`: long_context (0.25), hybrid_rag (0.2), graph_rag (0.2).
- `retrieval_recall`: dense_rag (0.7778), hybrid_rag (0.7778), graph_rag (0.7778).
- `tokens_per_query`: long_context (1522), dense_rag (1976), hybrid_rag (2104).
- `p95_latency`: long_context (2.723e+04), rolling_summary (6.671e+04), dense_rag (8.085e+04).
- `total_cost`: long_context (0.007265), dense_rag (0.009772), graph_rag (0.009975).
- `memory_update_accuracy`: no measured systems.
- `state_recovery_time`: no measured systems.

## Notes

Rankings are based on measured database metric rows and confidence intervals. Ties are flagged in `metric_rankings.json` where confidence intervals overlap.
