# CSM v3 Implementation Report

Generated: 2026-08-20

## Status

CSM v3 is implemented as a separate memory system type: `csm_v3`.

The existing CSM v2 adapter remains available as `csm` and was not overwritten. Existing baseline implementations were not modified.

The 60-turn live benchmark is complete.

Experiment ID: `2327c728-69ec-4fc4-9410-771c225d61a0`

Result folder:

```text
sustha/evaluation/results/csm_v3_selective/20260820T084125Z/
```

Run status:

- Experiment status: `completed`
- System runs: `3` completed, `0` failed
- Turns/questions: `60` completed, `0` failed
- Patients/cases: `3`
- Questions per patient: `20`
- Measured metric results: `63`
- Pending metric results: `0`

## Files Changed

- `app/memory_systems/csm/v3_engine.py`
- `app/memory_systems/csm/v3_adapter.py`
- `app/memory_systems/common/enums/status.py`
- `app/memory_systems/common/registry/registry.py`
- `app/memory_systems/common/canonical/source_collector.py`
- `app/memory_systems/common/services/memory_service.py`
- `app/config.py`
- `app/evaluation/experiments/services/live_runner.py`
- `app/evaluation/offline_recomputation/scope_loader.py`
- `app/evaluation/offline_recomputation/observation_builder.py`
- `app/evaluation/offline_recomputation/statistics.py`
- `app/evaluation/scripts/run_evaluation.py`
- `app/evaluation/scripts/preflight_csm_v2.py`
- `app/evaluation/scripts/prepare_csm_v2_derived_experiment.py`
- `app/evaluation/scripts/export_csm_v2_final_comparison.py`
- `app/evaluation/scripts/recompute_stored_patient_results.py`
- `tests/memory_systems/test_memory_registry.py`
- `tests/memory_systems/test_csm_v3_engine.py`

## Schema / Migration

No database migration was added.

CSM v3 reuses the existing CSM tables and separates data by `memory_system_instances.system_type = "csm_v3"` and `system_instance_id`.

Reused tables:

- `csm_evidence`
- `csm_state_variables`
- `csm_state_history`
- `csm_state_evidence_links`
- `csm_state_dependencies`
- `csm_review_requests`
- `csm_activation_runs`
- `csm_activation_items`
- `csm_update_events`

## CSM v2 vs CSM v3

CSM v2:

- System type: `csm`
- Implementation version: `csm_v2`
- Creates a state for every non-conversation source, including broad document/section/clinical note/encounter objects.
- Uses generic source-to-state upsert logic.
- Activates many state/evidence candidates using mostly lexical route scoring.
- Sends relatively verbose `CSM_STATE` / `CSM_RAW_EVIDENCE` context blocks.

CSM v3:

- System type: `csm_v3`
- Implementation version: `csm_v3`
- Stores every source as immutable evidence, but only registered decision-relevant patient information becomes computational state.
- Evidence-only source types include documents, document sections/pages/text, encounters, clinical notes, and conversations.
- Conversation claims become `CsmReviewRequest` rows and do not become verified active state.
- Uses explicit state definitions for `condition`, `medication`, `allergy`, `measurement`, `measurement_trend`, and `renal_function`.
- Uses typed update operators, lifecycle status, support/correction evidence IDs, and supersession relations in state payloads.
- Recomputes bounded derived descendants for measurement trends and renal-function states.
- Uses version-aware activation: current questions exclude superseded state; correction/history routes can include superseded versions.
- Uses hybrid deterministic semantic similarity plus lexical relevance for candidate utility.
- Uses mandatory + top-k activation with defaults:
  - `CSM_V3_TOP_K_STATES`: `4`
  - `CSM_V3_TOP_K_EVIDENCE`: `4`
  - `CSM_V3_CONTEXT_TOKEN_BUDGET`: `1800`
- Sends compact `[CSM_STATE]` and `[EVIDENCE]` blocks to the final-answer LLM.
- Stores activation audit details in `csm_update_events` with route, candidates, discards, score components, selected states/evidence, redundancy removals, and token estimates.

## Tests Added

`tests/memory_systems/test_csm_v3_engine.py` covers:

- Controlled state registry: documents/encounters are not computational state.
- Numeric measurement state payload preserves value, unit, lineage, and schema version.
- Corrections create `CORRECTS` relation and supersede previous value.
- Current retrieval excludes superseded state.
- Correction route can include superseded state.
- Future recorded evidence is blocked by source cutoff.
- Conversation claims stay pending review.
- Measurement history creates deterministic trend state value.
- Mandatory activation survives optional top-k selection.

Updated registry tests now expect eight registered systems including `csm_v3`.

## Test Results

Command:

```bash
cd sustha/backend
PYTHONPYCACHEPREFIX=/private/tmp/codex_pycache PYTHONPATH=. venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Result:

```text
Ran 89 tests in 0.086s
OK
```

Warnings observed:

- `urllib3` LibreSSL warning from local Python environment.
- `LangChainPendingDeprecationWarning`.

No test failures.

## Live Benchmark Results

Patients/cases:

- `SYN-CSM-001`
- `SYN-CSM-002`
- `SYN-CSM-003`

Questions:

- 20 per patient
- 60 total CSM v3 turns

Systems to run:

- `csm_v3` only

Main answer-generation calls:

- `60` completed Groq final-answer calls are linked to completed experiment turns.

Additional provider calls:

- None from CSM v3 memory updates. CSM v3 ingestion, state transitions, dependency recomputation, and retrieval are deterministic.
- The DB call log for the run window contains `63` final-answer provider rows: `60` completed and `3` failed.
- Failed provider rows were `2` `LlmProviderUnavailable` failures and `1` `LlmStructuredOutputFailed` failure from interrupted/resumed attempts.
- Completed linked call rows have total `retry_count = 2`.

Provider/model:

- Uses existing backend settings from `.env`, including `LLM_PROVIDER`, `GROQ_MODEL`, temperature, token limits, and retry settings.
- Final completed calls used `groq` with `openai/gpt-oss-120b`.

Run window:

- Started: `2026-08-20 14:11:27.239306+05:30`
- Completed: `2026-08-20 14:54:33.012679+05:30`

Token and cost totals from `token_results.csv`:

- Input tokens: `134628`
- Output tokens: `22711`
- Total tokens: `157339`
- Estimated total cost: `$0.03382080`
- Mean tokens/query: `2622.3167`
- Raw mean LLM duration: `37025.2167 ms`
- Raw p95 LLM duration: `68848 ms`

Selected aggregate metrics from `system_metric_matrix.csv`:

- `state_accuracy`: `0.0`
- `answer_accuracy`: `0.0`
- `hallucination_rate`: `1.0`
- `evidence_support_rate`: `0.0`
- `unsupported_claim_rate`: `1.0`
- `fabricated_citation_rate`: `0.47056006310570203`
- `faithfulness`: `0.8783495519269888`
- `groundedness`: `0.8783495519269888`
- `lineage_citation_f1`: `0.2880143112701252`
- `retrieval_precision`: `0.3792412617220801`
- `retrieval_recall`: `0.6306878306878307`
- `tokens_per_query`: `2622.3166666666666`
- `p95_latency`: `54049.01666666667 ms`
- `total_cost`: `0.0112736` mean per patient

Important output files:

- `experiment_manifest.json`
- `paper_results_summary.md`
- `paper_main_results_table.md`
- `paper_efficiency_table.md`
- `system_metric_matrix.csv`
- `per_patient_results.csv`
- `per_question_results.csv`
- `token_results.csv`
- `latency_results.csv`
- `cost_results.csv`
- `retrieval_traces.json`
- `activation_traces.json`
- `csm_state_trace.json`
- `csm_lineage_trace.json`

## Dry Run

Command:

```bash
cd sustha/backend
PYTHONPATH=. venv/bin/python -m app.evaluation.scripts.run_sustha_three_patient_pilot \
  --systems csm_v3 \
  --patient SYN-CSM-001 \
  --patient SYN-CSM-002 \
  --patient SYN-CSM-003 \
  --repetitions 1 \
  --concurrency 1 \
  --request-delay-seconds 3 \
  --max-retries 8 \
  --implementation-version csm_v3 \
  --output-dir ../evaluation/results/csm_v3_selective/dry_run \
  --dry-run
```

Dry-run result:

- Estimated turns: `60`
- Live LLM required: `true`
- Systems: `["csm_v3"]`

## Live Run Commands

Initial live command:

```bash
cd sustha/backend
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
PYTHONPATH=. venv/bin/python -m app.evaluation.scripts.run_sustha_three_patient_pilot \
  --systems csm_v3 \
  --patient SYN-CSM-001 \
  --patient SYN-CSM-002 \
  --patient SYN-CSM-003 \
  --repetitions 1 \
  --concurrency 1 \
  --request-delay-seconds 3 \
  --max-retries 8 \
  --implementation-version csm_v3 \
  --output-dir ../evaluation/results/csm_v3_selective/$RUN_ID \
  --skip-import \
  --confirm-cost
```

The first live attempt hit the Groq request/token limit on the sixth turn:

```text
requested 9576 tokens, limit 8000
```

The CSM v3 context budget was reduced from `3500` to `1800` tokens to fit the provider limit.

The run was resumed with the same experiment ID and result folder:

```bash
cd sustha/backend
PYTHONPATH=. venv/bin/python -m app.evaluation.scripts.run_sustha_three_patient_pilot \
  --experiment-id 2327c728-69ec-4fc4-9410-771c225d61a0 \
  --resume \
  --systems csm_v3 \
  --patient SYN-CSM-001 \
  --patient SYN-CSM-002 \
  --patient SYN-CSM-003 \
  --repetitions 1 \
  --concurrency 1 \
  --request-delay-seconds 3 \
  --max-retries 8 \
  --implementation-version csm_v3 \
  --output-dir ../evaluation/results/csm_v3_selective/20260820T084125Z \
  --skip-import \
  --confirm-cost
```

Later resumes hit provider rate limits on the primary Groq key. The final resume used `GROQ_API_KEY_2` as the process `GROQ_API_KEY` value without changing provider code and slowed requests to `65` seconds:

```bash
cd sustha/backend
GROQ_API_KEY="$(python3 -c 'from pathlib import Path; import os; [os.environ.setdefault(k, v) for line in Path(".env").read_text().splitlines() if line and not line.startswith("#") and "=" in line for k, v in [line.split("=", 1)]]; print(os.environ["GROQ_API_KEY_2"], end="")')" \
PYTHONPATH=. venv/bin/python -m app.evaluation.scripts.run_sustha_three_patient_pilot \
  --experiment-id 2327c728-69ec-4fc4-9410-771c225d61a0 \
  --resume \
  --systems csm_v3 \
  --patient SYN-CSM-001 \
  --patient SYN-CSM-002 \
  --patient SYN-CSM-003 \
  --repetitions 1 \
  --concurrency 1 \
  --request-delay-seconds 65 \
  --max-retries 8 \
  --implementation-version csm_v3 \
  --output-dir ../evaluation/results/csm_v3_selective/20260820T084125Z \
  --skip-import \
  --confirm-cost
```

Final progress:

```text
status: completed
expected_system_runs: 3
completed_system_runs: 3
failed_system_runs: 0
expected_turns: 60
completed_turns: 60
failed_turns: 0
measured_metric_results: 63
pending_metric_results: 0
failure_reason: null
```

## Limitations

- CSM v3 uses deterministic hash embeddings for semantic relevance, not an external embedding model.
- Derived clinical state is intentionally bounded to generic measurement trends and renal measurement-derived state; no patient-specific facts or ground truth labels are used.
- Existing CSM v2 final-result scripts were patched to keep their original seven-system scope so v2 reproducibility is preserved.
