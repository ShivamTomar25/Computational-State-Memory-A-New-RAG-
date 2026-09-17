# Sustha Backend

FastAPI backend for the Sustha Medical Memory Platform.

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Supabase Storage

Supabase is used only for private object storage. PostgreSQL, Doctor JWT authentication, patient ownership, and clinical authorization remain in FastAPI and the existing PostgreSQL database.

Create a private Supabase Storage bucket named `clinical-documents`. Keep public access disabled. If the dashboard offers bucket file limits, configure the allowed MIME types to:

```text
application/pdf
text/plain
application/vnd.openxmlformats-officedocument.wordprocessingml.document
```

Use a maximum file size such as `20971520` bytes, which is 20 MiB. Do not use real patient files during early development.

Backend environment variables:

```text
SUPABASE_URL=
SUPABASE_SECRET_KEY=
SUPABASE_STORAGE_BUCKET=clinical-documents
SUPABASE_SIGNED_UPLOAD_EXPIRY_SECONDS=600
SUPABASE_SIGNED_DOWNLOAD_EXPIRY_SECONDS=300
DOCUMENT_MAX_FILE_SIZE_BYTES=20971520
DOCUMENT_ALLOWED_CONTENT_TYPES=application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document
DOCUMENT_STORAGE_ENVIRONMENT=development
```

`SUPABASE_SECRET_KEY` is a backend-only privileged key. Never put it in frontend environment variables, Swagger examples, screenshots, commits, or browser code. Server-side keys may bypass Supabase RLS, so FastAPI must verify doctor authentication, patient ownership, and future document ownership before requesting storage operations.

Storage readiness is available at:

```bash
curl http://127.0.0.1:8000/health/storage
```

If Supabase is not configured, the app can still start and storage readiness returns `not_configured`. Storage-dependent operations fail with a clear configuration error.

Run a safe configuration-only verification:

```bash
python -m app.storage.verify
```

Run an explicit synthetic write verification only after configuring a test project and private bucket:

```bash
python -m app.storage.verify --write
```

The write verification uploads a synthetic probe object outside patient paths, creates a short-lived signed download, then attempts cleanup. It prints no credentials and no full signed URL.

## Storage Architecture

Storage code is isolated under `app/storage`:

```text
app/storage/interface.py
app/storage/schemas.py
app/storage/exceptions.py
app/storage/path_builder.py
app/storage/file_policy.py
app/storage/dependencies.py
app/storage/health.py
app/storage/verify.py
app/storage/supabase/client.py
app/storage/supabase/provider.py
```

Future Document code should depend on `StorageProvider` from `app/storage/interface.py`, not on the Supabase SDK. The storage package does not import Doctor, Patient, Document, RAG, Evidence, or CSM modules.

Generated object paths use only environment, patient UUID, document UUID, object category, and a sanitized filename:

```text
development/patients/{patient_uuid}/documents/{document_uuid}/original/{safe_filename}
development/patients/{patient_uuid}/documents/{document_uuid}/derived/extracted-text.txt
development/patients/{patient_uuid}/documents/{document_uuid}/derived/metadata.json
development/patients/{patient_uuid}/documents/{document_uuid}/derived/pages/{page_number}.png
```

Signed uploads are created by the backend for a backend-generated path. The current Supabase Python SDK method does not accept a custom signed-upload expiry argument, so `SUPABASE_SIGNED_UPLOAD_EXPIRY_SECONDS` is kept as the backend's future upload-completion deadline, not as a provider-enforced token lifetime. Signed downloads are short-lived private URLs controlled by `SUPABASE_SIGNED_DOWNLOAD_EXPIRY_SECONDS` and must not be stored permanently or logged.

## Supabase Dashboard Setup

In Supabase:

```text
1. Open your project.
2. Go to Project Settings.
3. Open API Keys.
4. Copy the Project URL into backend/.env as SUPABASE_URL.
5. Copy the backend secret/service-role credential into backend/.env as SUPABASE_SECRET_KEY.
6. Go to Storage.
7. Create bucket clinical-documents.
8. Keep Public bucket disabled.
9. Configure bucket MIME types and size limits when available.
```

Publishable or anon keys are for appropriate client-side contexts only. Secret or service-role keys are backend-only and may bypass RLS.

## Backend Tests

Storage unit tests use fake clients and do not call Supabase:

```bash
python -m unittest discover -s tests -p "test_*.py"
```
