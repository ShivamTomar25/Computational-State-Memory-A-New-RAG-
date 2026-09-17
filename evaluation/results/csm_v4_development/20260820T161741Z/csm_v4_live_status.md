# CSM v4 Live Run Status

Generated: 2026-08-20T16:17:41Z

## Current State

- Experiment ID: `179bb8b4-2640-4619-89cb-3cd509e7c8e7`
- System: `csm_v4`
- Target scope: 3 patients x 20 questions x 1 repetition = 60 final-answer generations
- Completed live turns: 60/60
- Patient 1 (`SYN-CSM-001`): 20/20 completed
- Patient 2 (`SYN-CSM-002`): 20/20 completed
- Patient 3 (`SYN-CSM-003`): 20/20 completed
- Stop reason: none
- Final CSM v4 scientific matrix status: exported
- Live output directory: `evaluation/results/sustha_three_patient_pilot/20260820T185652Z`
- Evaluator-compatible output directory: `evaluation/results/csm_v4_evaluator_compatible/20260820T190017Z`

## Completed Non-Provider Work

- CSM v2 vs CSM v3 per-question diagnosis completed with zero new LLM calls.
- CSM v4 implementation added as a separate system, leaving `csm` and `csm_v3` unchanged.
- Offline CSM v4 gates passed before live generation.
- Backend unittest discovery passed: 110 tests OK.
- `export_csm_v4_evaluator_compatible.py` was added and used for the final V2/V3/V4 comparison.

## Key Artifacts

- Diagnosis: `evaluation/results/csm_v4_development/20260820T111118Z/csm_v2_vs_v3_question_diagnosis.csv`
- Diagnosis report: `evaluation/results/csm_v4_development/20260820T111118Z/csm_v2_vs_v3_failure_summary.md`
- Passing offline gate: `evaluation/results/csm_v4_development/20260820T122949Z/csm_v4_offline_gate_summary.md`
- CSM v4 exporter: `backend/app/evaluation/scripts/export_csm_v4_evaluator_compatible.py`
- Live run export: `evaluation/results/sustha_three_patient_pilot/20260820T185652Z`
- Final CSM v2/v3/v4 report: `evaluation/results/csm_v4_evaluator_compatible/20260820T190017Z/17_final_report.md`
- Final CSM v2/v3/v4 comparison: `evaluation/results/csm_v4_evaluator_compatible/20260820T190017Z/13_csm_v2_v3_v4_comparison.csv`

## Resume Command

No resume command is needed now. The live run completed.

## Final Export Command

Already completed from `sustha/backend`:

```bash
env PYTHONPYCACHEPREFIX=/tmp/csm_pycache PYTHONPATH=. \
  venv/bin/python -m app.evaluation.scripts.export_csm_v4_evaluator_compatible \
  --experiment-id 179bb8b4-2640-4619-89cb-3cd509e7c8e7 \
  --tests-note "backend unittest discovery: 110 tests OK; csm_v4 exporter py_compile OK"
```

Final export status:

- Export completed successfully.
- New LLM calls during export: `0`
- Stored answers modified by export: `NO`
- Ground truth modified by export: `NO`
- Baseline values changed: `NO`
