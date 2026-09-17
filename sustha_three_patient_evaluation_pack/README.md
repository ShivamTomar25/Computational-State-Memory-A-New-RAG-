# Sustha CSM Three-Patient Evaluation Pack

Version: sustha-csm-three-patient-pilot-v1.0

Synthetic evaluation record - not for clinical use.

## Contents

- One synthetic doctor account
- Three synthetic patient profiles
- Structured Patient Information records
- 18 selectable-text PDFs plus exact `.txt` copies
- Source conversations with supported and unsupported proposals
- Chronological timelines
- Expected CSM state snapshots
- 60 evaluation questions with ground truth and retrieval labels
- Common single-turn and multi-turn scripts for all seven systems
- Metric applicability mapping for all 21 metrics
- Paper-ready CSV and Markdown files

## Manual execution order

1. Register the synthetic doctor using `doctor/registration.json`.
2. Create each patient using `patients/<code>/patient.json`.
3. Enter structured records in the order listed in `structured_information.json`.
4. Upload PDFs in filename order from `patients/<code>/documents/` using `document_metadata.json`.
5. Add source conversations from `source_conversations.json`.
6. Initialize all seven memory systems.
7. Synchronize all systems at the same history cutoff.
8. Run every question in `benchmark/common_single_turn_questions.json` as a fresh conversation for each system.
9. Run the controlled scripts in `benchmark/common_multi_turn_script.json`.
10. Start the evaluation experiment and inspect matrix, rankings, statistics, claims, citations, hallucinations, retrieval traces, temporal traces, corrections, conflicts, and CSM state traces.
11. Export CSV/JSON results and populate `paper/expected_result_tables.csv` with measured values only.

## Critical controls

- Do not ingest any file under `ground_truth.json`, `benchmark/ground_truth.json`, or the `paper/` directory into memory systems.
- Respect each question's `source_cutoff`.
- Use identical LLM and retrieval settings across systems.
- Treat unsupported chat claims as pending review, not active CSM state.
- Count duplicate-family sources as correlated evidence, not independent confirmation.
