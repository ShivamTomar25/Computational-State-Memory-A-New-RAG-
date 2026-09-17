# Sustha

Research prototype for clinically grounded patient-memory systems, retrieval-augmented medical question answering, and observation-level evaluation of Computational State Memory.

Sustha is a full-stack research platform for comparing seven memory architectures on synthetic clinical cases. The central research question is whether a structured, evidence-linked memory representation can preserve patient state, temporal context, source lineage, and correction history better than conventional retrieval-only or summary-only baselines.

This repository is intended for academic review and reproducibility. It includes the FastAPI backend, React frontend, memory-system implementations, synthetic evaluation pack, offline recomputation pipeline, and the latest final CSM v2 comparison artifacts.

Important: this is a research prototype using synthetic or deidentified-style data controls. It is not a clinical device and must not be used for real patient care.

## Contents

- [Research Focus](#research-focus)
- [Repository Structure](#repository-structure)
- [System Architecture](#system-architecture)
- [Backend](#backend)
- [Frontend](#frontend)
- [Memory Systems](#memory-systems)
- [Computational State Memory v2](#computational-state-memory-v2)
- [Evaluation Framework](#evaluation-framework)
- [Latest Offline Evaluation](#latest-offline-evaluation)
- [Reproducibility](#reproducibility)
- [Setup](#setup)
- [Running Locally](#running-locally)
- [Tests And Verification](#tests-and-verification)
- [Security, Privacy, And Ethics](#security-privacy-and-ethics)
- [Known Limitations](#known-limitations)
- [Academic Review Checklist](#academic-review-checklist)

## Research Focus

Sustha studies memory in longitudinal clinical question answering. The platform compares memory systems that receive the same synthetic patient history and answer the same controlled evaluation questions.

The implemented comparison includes:

1. Long Context
2. Rolling Summary
3. Dense RAG
4. Hybrid RAG
5. GraphRAG
6. HippoRAG
7. Computational State Memory (CSM)

The CSM line of work is the main contribution. Instead of treating the patient record only as retrievable text, CSM builds typed state variables with evidence links, current values, validity windows, confidence, conflict handling, and dependency traces. The evaluation is designed to test whether that structured state helps with clinical-memory tasks such as current medication status, corrected conditions, temporal interpretation, and source-grounded answers.

## Repository Structure

```text
sustha/
  backend/                              FastAPI backend, database models, memory systems, LLM layer, evaluation API
  frontend/                             React/Vite/Tailwind clinical and research UI
  evaluation/results/                   Generated final offline evaluation artifacts
  sustha_three_patient_evaluation_pack/ Synthetic benchmark pack for three patients
```

Important subdirectories:

```text
backend/app/
  doctor/                    Doctor registration, authentication, authorization helpers
  patient/                   Patient ownership and patient workspace models
  patient_information/       Encounters, conditions, medications, allergies, measurements, notes
  document/                  Document metadata, upload lifecycle, document access control
  document_processing/       Text extraction, page/section building, artifact generation
  storage/                   Storage abstraction and Supabase private-object provider
  memory_systems/            Seven memory-system implementations and shared registry
  llm/                       Provider abstraction, Groq-backed grounded answer generation
  evaluation/                Benchmark datasets, experiments, metrics, offline recomputation
  performance/               Caching, timing, instrumentation, profiling middleware
  health/                    Health and storage readiness routes
```

## System Architecture

At a high level, Sustha has four layers.

```text
React frontend
  |
  | HTTP/JSON, bearer token authentication
  v
FastAPI backend
  |
  | SQLAlchemy ORM
  v
PostgreSQL clinical and experiment database
  |
  +-- Supabase Storage for private clinical document objects
  +-- Optional Groq provider for answer generation
  +-- Offline evaluation scripts for reproducible result recomputation
```

The backend follows a modular domain layout. Patient ownership is enforced before patient-scoped reads and writes. Memory systems share canonical sources but keep system-private conversation state isolated. Evaluation results are generated from stored turn-level data rather than from ad hoc spreadsheet edits.

## Backend

The backend is a FastAPI application with SQLAlchemy models and Pydantic schemas. It is started from:

```text
backend/app/main.py
```

Registered routers include:

| Area | Example routes |
| --- | --- |
| Health | `/health`, `/health/storage` |
| Doctors | `/api/doctors/register`, `/api/doctors/login`, `/api/doctors/me` |
| Patients | `/api/patients`, `/api/patients/{patient_id}` |
| Patient information | `/api/patients/{patient_id}/conditions`, `/medications`, `/allergies`, `/measurements`, `/notes`, `/encounters` |
| Documents | `/api/patients/{patient_id}/documents` |
| Memory systems | `/api/memory-systems`, `/api/patients/{patient_id}/memory-systems/{system_type}/retrieve` |
| CSM | `/api/patients/{patient_id}/csm`, `/states`, `/evidence`, `/conflicts`, `/reviews` |
| LLM | `/api/llm/status` |
| Evaluation | `/api/evaluation/metrics`, `/datasets`, `/experiments`, `/results`, `/rankings`, `/matrix`, `/statistics` |
| Performance | `/api/performance/summary`, `/routes`, `/database`, `/cache`, `/jobs` |

Core backend capabilities:

- Doctor registration, password hashing, JWT authentication, and patient ownership checks.
- Structured patient information CRUD for longitudinal clinical records.
- Private document upload lifecycle with storage policy validation.
- PDF, DOCX, and plain-text extraction pipeline.
- Canonical patient-source construction for memory ingestion.
- Seven memory-system adapters behind a common registry.
- Grounded answer generation through an LLM provider abstraction.
- Turn-level experiment tracking, claims, citations, retrieval traces, costs, latency, and metrics.
- Performance instrumentation through request IDs, request timing, compression, cache abstraction, and slow-query tooling.

## Frontend

The frontend is a React 18, Vite, JavaScript, and Tailwind application.

Main entry points:

```text
frontend/src/main.jsx
frontend/src/App.jsx
```

The UI includes clinical workflow pages and research/evaluation pages:

- Login and doctor registration
- Doctor patient list and patient workspace
- Patient information editor
- Document upload and medical document viewer
- Patient timeline
- Evidence explorer
- Memory-system registry and system workspace
- Computational State Memory dashboard
- Patient chat and conversation history
- Research dashboard
- Evaluation dashboard, experiment creation, experiment detail, dataset management, human review
- System health, performance, background jobs, export center, audit pages

The frontend talks to the backend through local service modules such as:

```text
frontend/src/services/memorySystemsApi.js
frontend/src/services/evaluationApi.js
frontend/src/pages/upload_document/documentApi.js
frontend/src/pages/patient_information/patientInformationApi.js
```

## Memory Systems

The seven compared systems live under:

```text
backend/app/memory_systems/
```

| System | Implementation status and role |
| --- | --- |
| `long_context` | Stores ordered context entries and retrieves chronologically within a token budget. |
| `rolling_summary` | Maintains recent-window items and summary snapshots. |
| `dense_rag` | Chunks canonical sources and stores deterministic local embedding vectors. |
| `hybrid_rag` | Combines dense retrieval, lexical matching, and reciprocal-rank fusion. |
| `graph_rag` | Stages graph-style text units and graph-oriented retrieval records. |
| `hippo_rag` | Stages passage nodes and HippoRAG-style index records. |
| `csm` | Builds typed, evidence-linked state variables for patient memory. |

Shared memory infrastructure is in:

```text
backend/app/memory_systems/common/
```

It provides canonical source collection, embedding providers, registry abstractions, repositories, retrieval chunking, token-budget control, ingestion runs, retrieval traces, and conversation workflows.

## Computational State Memory v2

CSM v2 is implemented in:

```text
backend/app/memory_systems/csm/v2_engine.py
backend/app/memory_systems/csm/service.py
backend/app/memory_systems/csm/models.py
backend/app/memory_systems/csm/adapter.py
backend/app/memory_systems/csm/router.py
```

The CSM representation is designed around:

- State variables with state type, state key, current value, status, confidence, validity windows, and versioning.
- Evidence records linked to canonical patient sources.
- State-evidence links with contribution type and contribution weight.
- Dependency traces between state variables and evidence records.
- Conflict and review surfaces for clinical correction workflows.
- Activation traces showing which state/evidence records were used during retrieval.

For evaluation, CSM v2 is not judged only by final answer text. The offline evaluator also audits state snapshots, state-key mapping, lineage resolution, dependency traces, activation evidence, temporal assertions, correction recovery, calibration, citations, and retrieval identifiers.

## Evaluation Framework

Evaluation code is in:

```text
backend/app/evaluation/
```

Main components:

| Component | Path |
| --- | --- |
| Dataset models and validators | `backend/app/evaluation/datasets/` |
| Experiment models and services | `backend/app/evaluation/experiments/` |
| Metric implementations | `backend/app/evaluation/metrics/` |
| Human review models | `backend/app/evaluation/judges/human_review/` |
| Evaluation API routers | `backend/app/evaluation/api/` |
| Offline recomputation | `backend/app/evaluation/offline_recomputation/` |
| Reproducibility scripts | `backend/app/evaluation/scripts/` |

The synthetic benchmark pack is in:

```text
sustha_three_patient_evaluation_pack/
```

It contains:

- One synthetic doctor account
- Three synthetic patient profiles
- Structured patient records
- Source conversations
- Timelines
- Expected CSM state snapshots
- Ground-truth files
- Expected relevant sources
- 60 evaluation questions
- Metric applicability mapping for 21 paper metrics
- Paper support tables

Critical benchmark controls:

- Do not ingest `ground_truth.json`, `benchmark/ground_truth.json`, or `paper/` into any memory system.
- Respect question source cutoffs.
- Use identical LLM and retrieval settings across systems.
- Treat unsupported chat claims as pending review, not active patient state.
- Count duplicate-family evidence as correlated, not independently confirmatory.

## Latest Offline Evaluation

The latest retained final result is:

```text
evaluation/results/csm_v2_final_comparison_offline_v3/SYN-CSM-001/repetition_1/20260722T115832Z/
```

Final comparison identifiers:

| Field | Value |
| --- | --- |
| Completed derived experiment | `b9570d90-7be3-4dbf-9063-535811b2e970` |
| Source experiment | `2ecee123-ddc0-4072-a823-885c12fc98a6` |
| Abandoned/superseded experiment | `38bfe0ac-d975-426a-9975-b4b1a3a62be2` |
| Patient | `SYN-CSM-001` |
| Repetition | `1` |
| Systems | `7` |
| Questions per system | `20` |
| Completed turns | `140` |
| Metric observations | `4060` |
| Paper metrics | `21` |
| LLM calls during offline recomputation | `0` |
| Existing aggregate metric rows reused | `false` |

The scope validator passed:

```text
included_turns = 140
completed_turns = 140
systems = 7
questions_per_system = 20
errors = []
```

The answer preservation audit passed:

```text
provider_invocations_during_recomputation = 0
hashes_match = true
answers_modified = false
turn_answer_hash_count = 140
```

Key final artifacts:

| Artifact | Purpose |
| --- | --- |
| `system_metric_matrix.csv` | Full system-by-metric matrix with observation counts and confidence intervals. |
| `metric_rankings.csv` | Rankings computed from observation-level metric rows. |
| `paper_complete_21_metric_matrix.csv` | Paper-ready 21-metric table. |
| `metric_observations.csv` | 4060 metric observations used to build matrix and rankings. |
| `claim_matching_audit.csv` | Claim-level true positive, false positive, false negative, and insufficiency audit. |
| `answer_f1_audit.csv` | True claim-level precision, recall, and F1 per turn. |
| `claim_support_audit.csv` | Deterministic support classifications for generated factual claims. |
| `citation_resolution_audit.csv` | Citation resolution and classification. |
| `retrieval_identifier_resolution_audit.csv` | Canonical source resolution for retrieval identifiers. |
| `csm_activation_audit.csv` | CSM activation evidence and canonical source links. |
| `csm_lineage_resolution_audit.csv` | State-to-evidence-to-canonical-source lineage audit. |
| `csm_dependency_trace_audit.csv` | CSM dependency trace audit. |
| `state_comparison_audit.csv` | Expected state snapshot and state-memory comparison support. |
| `temporal_assertion_audit.csv` | Temporal relation evaluation rows. |
| `decision_label_audit.csv` | Decision-label audit rows. |
| `correction_recovery_audit.csv` | Correction recovery rows. |
| `calibration_audit.csv` | Confidence calibration rows. |
| `latency_definition_audit.csv` | Latency definition and stored latency source rows. |
| `answer_preservation_audit.json` | Hash audit proving stored answer text was not modified. |
| `comparison_provenance.json` | Offline mode, experiment lineage, and no-LLM provenance. |
| `metric_recomputation_manifest.json` | Manifest with output files and SHA-256 hashes. |

Representative CSM v2 values from the final 21-metric paper table:

| Metric | CSM value | n |
| --- | ---: | ---: |
| answer_accuracy | 0.1523 | 19 |
| hallucination_rate | 0.0000 | 19 |
| evidence_support_rate | 0.6096 | 19 |
| unsupported_claim_rate | 0.0000 | 19 |
| fabricated_citation_rate | 0.0000 | 19 |
| faithfulness | 0.6096 | 19 |
| groundedness | 0.6096 | 19 |
| expected_calibration_error | 0.0745 | 16 |
| lineage_citation_f1 | 0.1537 | 19 |
| correction_recovery | 0.5385 | 13 |
| retrieval_precision | 0.0749 | 20 |
| retrieval_recall | 0.1809 | 20 |
| memory_update_accuracy | 0.2143 | 7 |
| state_recovery_time | 1.0000 | 11 |

These numbers should be interpreted as a single synthetic-patient pilot result. They are useful for engineering validation and research-method demonstration, not for clinical deployment claims.

## Reproducibility

The final offline recomputation command is:

```bash
cd "/Users/shivamtomar/Desktop/Project - 1/sustha/backend"
venv/bin/python -m app.evaluation.scripts.recompute_stored_patient_results \
  --experiment-id b9570d90-7be3-4dbf-9063-535811b2e970 \
  --source-experiment-id 2ecee123-ddc0-4072-a823-885c12fc98a6 \
  --abandoned-experiment-id 38bfe0ac-d975-426a-9975-b4b1a3a62be2 \
  --patient SYN-CSM-001 \
  --repetition 1 \
  --output-root ../evaluation/results/csm_v2_final_comparison_offline_v3
```

The script recomputes metrics from stored turn-level data. It does not rerun answer generation, does not call Groq, does not regenerate CSM answers, and does not use legacy aggregate evaluator rows.

Before running, inspect the CLI contract:

```bash
cd backend
venv/bin/python -m app.evaluation.scripts.recompute_stored_patient_results --help
```

Final artifact paths for the latest retained output:

```text
FINAL_MATRIX=evaluation/results/csm_v2_final_comparison_offline_v3/SYN-CSM-001/repetition_1/20260722T115832Z/system_metric_matrix.csv
FINAL_RANKINGS=evaluation/results/csm_v2_final_comparison_offline_v3/SYN-CSM-001/repetition_1/20260722T115832Z/metric_rankings.csv
FINAL_PAPER_TABLE=evaluation/results/csm_v2_final_comparison_offline_v3/SYN-CSM-001/repetition_1/20260722T115832Z/paper_complete_21_metric_matrix.csv
```

## Setup

### Backend prerequisites

- Python 3.9 or newer
- PostgreSQL
- Optional Supabase project for private document storage
- Optional Groq API key for live grounded answer generation

Backend setup:

```bash
cd sustha/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` for local PostgreSQL and any external providers:

```text
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/project_1
JWT_SECRET_KEY=change-this-development-secret
GROQ_API_KEY=
SUPABASE_URL=
SUPABASE_SECRET_KEY=
```

Do not commit `.env`, service-role keys, or real clinical data.

### Frontend prerequisites

- Node.js
- npm

Frontend setup:

```bash
cd sustha/frontend
npm install
```

## Running Locally

Start the backend:

```bash
cd sustha/backend
source venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

or:

```bash
cd sustha/backend
npm run start
```

Start the frontend:

```bash
cd sustha/frontend
npm run dev
```

Useful local checks:

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/storage
curl http://127.0.0.1:8000/api/llm/status
```

## Storage

Supabase is used as a private object-storage provider. Database ownership and authorization remain in FastAPI and PostgreSQL.

Storage implementation:

```text
backend/app/storage/interface.py
backend/app/storage/path_builder.py
backend/app/storage/file_policy.py
backend/app/storage/supabase/provider.py
backend/app/storage/health.py
backend/app/storage/verify.py
```

Recommended bucket:

```text
clinical-documents
```

Supported document MIME types:

```text
application/pdf
text/plain
application/vnd.openxmlformats-officedocument.wordprocessingml.document
```

Safe storage verification:

```bash
cd sustha/backend
python -m app.storage.verify
```

Explicit synthetic write probe:

```bash
cd sustha/backend
python -m app.storage.verify --write
```

## Tests And Verification

Backend compile check:

```bash
cd sustha/backend
/usr/bin/env PYTHONPYCACHEPREFIX=/private/tmp/sustha-pycache venv/bin/python -m compileall app
```

Backend unit tests:

```bash
cd sustha/backend
/usr/bin/env PYTHONPYCACHEPREFIX=/private/tmp/sustha-pycache venv/bin/python -m unittest discover -s tests -p "test_*.py"
```

Frontend production build:

```bash
cd sustha/frontend
npm run build
```

Current test coverage includes storage policy, storage health, Supabase provider behavior with fake clients, document processing, memory registry/workflows, CSM v2 engine behavior, LLM security/provider checks, evaluation metric calculators, evaluation registry/dataset validation, and performance instrumentation.

## Security, Privacy, And Ethics

Sustha is designed for synthetic clinical-memory research. The codebase includes safety controls that should be preserved in future work:

- `LLM_EXTERNAL_DATA_MODE=synthetic_or_deidentified`
- `LLM_ALLOW_IDENTIFIABLE_CLINICAL_DATA=false`
- Backend-only storage secret handling
- No service-role key in frontend code
- Patient ownership checks for patient-scoped APIs
- System-private conversation memory isolation
- Offline evaluation path that avoids new provider calls
- Answer-preservation hashes for final recomputation

Do not use real patient data unless the project is reviewed under the appropriate institutional, legal, privacy, and security process. Synthetic data is sufficient for reproducing the current evaluation.

## Known Limitations

- The latest result is a single-patient, one-repetition synthetic pilot.
- The offline evaluator is deterministic and audit-oriented, but it is still an approximation over stored structured claims, citations, retrieval traces, and CSM state records.
- OCR is not implemented; the document pipeline detects OCR requirements but processes selectable text.
- The repository currently uses SQLAlchemy metadata creation through `init_db()` rather than a full Alembic migration history.
- GraphRAG and HippoRAG are represented with local/staged providers where external graph-construction dependencies are unavailable.
- Live LLM generation requires provider configuration; without a key, the backend returns a clean `not_configured` status.
- The evaluation result should be treated as engineering evidence for a research prototype, not as clinical validation.

## Academic Review Checklist

For a reviewer, the strongest files to inspect are:

```text
backend/app/memory_systems/csm/v2_engine.py
backend/app/memory_systems/csm/models.py
backend/app/evaluation/offline_recomputation/observation_builder.py
backend/app/evaluation/offline_recomputation/exporter.py
backend/app/evaluation/scripts/recompute_stored_patient_results.py
sustha_three_patient_evaluation_pack/README.md
evaluation/results/csm_v2_final_comparison_offline_v3/SYN-CSM-001/repetition_1/20260722T115832Z/metric_recomputation_manifest.json
evaluation/results/csm_v2_final_comparison_offline_v3/SYN-CSM-001/repetition_1/20260722T115832Z/paper_complete_21_metric_matrix.csv
```

Questions the repository is prepared to answer:

1. What data entered each memory system?
2. Which stored answer text was evaluated?
3. Were any answers regenerated during final evaluation?
4. Which claims were matched to ground truth?
5. Which claims were supported, partially supported, unsupported, or insufficient-evidence statements?
6. Which citations resolved to canonical sources?
7. Which retrieval identifiers resolved to expected evidence?
8. Which CSM states, evidence records, and dependencies contributed to answers?
9. Which metric observations produced the final matrix and rankings?
10. What are the exact output files and SHA-256 hashes?

The current latest retained evaluation folder answers these through the audit files listed above.
