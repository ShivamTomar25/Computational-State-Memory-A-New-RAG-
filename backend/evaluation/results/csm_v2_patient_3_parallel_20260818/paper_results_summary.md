# Sustha Three-Patient Pilot Results

This is a synthetic pilot/integration benchmark. It should not be interpreted as evidence of broad clinical generalization.

Experiment status: `completed`.
Completed turns: `140` of `140`.
Measured metric rows: `105`.

## Top Systems By Metric
- `state_accuracy`: long_context (0), rolling_summary (0), dense_rag (0).
- `temporal_consistency`: no measured systems.
- `decision_f1`: no measured systems.
- `answer_accuracy`: long_context (0), rolling_summary (0), dense_rag (0).
- `hallucination_rate`: long_context (1), rolling_summary (1), dense_rag (1).
- `evidence_support_rate`: long_context (0), rolling_summary (0), dense_rag (0).
- `unsupported_claim_rate`: long_context (1), rolling_summary (1), dense_rag (1).
- `fabricated_citation_rate`: dense_rag (0.2051), hybrid_rag (0.2162), hippo_rag (0.2286).
- `faithfulness`: rolling_summary (1), dense_rag (1), hybrid_rag (1).
- `groundedness`: rolling_summary (1), dense_rag (1), hybrid_rag (1).
- `expected_calibration_error`: hybrid_rag (0.7406), graph_rag (0.7764), dense_rag (0.7911).
- `lineage_citation_f1`: long_context (0.4), dense_rag (0.3019), hybrid_rag (0.2745).
- `contradiction_handling`: no measured systems.
- `correction_recovery`: no measured systems.
- `retrieval_precision`: long_context (0.75), hybrid_rag (0.2857), dense_rag (0.2619).
- `retrieval_recall`: hybrid_rag (0.8571), dense_rag (0.7857), hippo_rag (0.7857).
- `tokens_per_query`: long_context (1607), dense_rag (1947), hippo_rag (2014).
- `p95_latency`: dense_rag (2.468e+04), long_context (3.235e+04), hybrid_rag (3.311e+04).
- `total_cost`: long_context (0.007811), dense_rag (0.009541), graph_rag (0.00987).
- `memory_update_accuracy`: no measured systems.
- `state_recovery_time`: no measured systems.

## Notes

Rankings are based on measured database metric rows and confidence intervals. Ties are flagged in `metric_rankings.json` where confidence intervals overlap.
