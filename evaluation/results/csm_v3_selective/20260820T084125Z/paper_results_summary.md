# Sustha Three-Patient Pilot Results

This is a synthetic pilot/integration benchmark. It should not be interpreted as evidence of broad clinical generalization.

Experiment status: `completed`.
Completed turns: `60` of `60`.
Measured metric rows: `48`.

## Top Systems By Metric
- `state_accuracy`: csm_v3 (0).
- `temporal_consistency`: no measured systems.
- `decision_f1`: no measured systems.
- `answer_accuracy`: csm_v3 (0).
- `hallucination_rate`: csm_v3 (1).
- `evidence_support_rate`: csm_v3 (0).
- `unsupported_claim_rate`: csm_v3 (1).
- `fabricated_citation_rate`: csm_v3 (0.4706).
- `faithfulness`: csm_v3 (0.8783).
- `groundedness`: csm_v3 (0.8783).
- `expected_calibration_error`: csm_v3 (0.8933).
- `lineage_citation_f1`: csm_v3 (0.288).
- `contradiction_handling`: csm_v3 (0).
- `correction_recovery`: csm_v3 (0).
- `retrieval_precision`: csm_v3 (0.3792).
- `retrieval_recall`: csm_v3 (0.6307).
- `tokens_per_query`: csm_v3 (2622).
- `p95_latency`: csm_v3 (5.405e+04).
- `total_cost`: csm_v3 (0.01127).
- `memory_update_accuracy`: no measured systems.
- `state_recovery_time`: no measured systems.

## Notes

Rankings are based on measured database metric rows and confidence intervals. Ties are flagged in `metric_rankings.json` where confidence intervals overlap.
