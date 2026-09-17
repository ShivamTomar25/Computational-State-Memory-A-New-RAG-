import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  Archive,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  Download,
  FileText,
  FolderOpen,
  Info,
  Loader2,
  LogOut,
  RefreshCcw,
  RotateCcw,
  ShieldCheck,
  Upload,
  UserRound,
  X,
} from "lucide-react";

import { clearAuthSession, getCurrentDoctor, getStoredDoctor } from "../login_page/authApi";
import { getPatient } from "../patient_shared/patientApi";
import {
  archiveDocument,
  getDocumentArtifacts,
  getDocumentDownloadUrl,
  getDocumentPages,
  getDocumentProcessing,
  getDocumentSections,
  getDocumentText,
  getDocumentViewUrl,
  listDocuments,
  processDocument,
  reconcileDocuments,
  restoreDocument,
  uploadDocument,
} from "./documentApi";
import { cacheCsmDocument, syncCsm } from "../computational_state_memory/csmService";

const maxFileSize = 20 * 1024 * 1024;
const allowedTypes = {
  "application/pdf": "PDF",
  "text/plain": "TXT",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
};

const documentTypes = [
  { value: "lab_report", label: "Lab report" },
  { value: "prescription", label: "Prescription" },
  { value: "discharge_summary", label: "Discharge summary" },
  { value: "imaging_report", label: "Imaging report" },
  { value: "consultation_note", label: "Consultation note" },
  { value: "referral", label: "Referral" },
  { value: "procedure_report", label: "Procedure report" },
  { value: "insurance_document", label: "Insurance document" },
  { value: "identity_document", label: "Identity document" },
  { value: "consent_form", label: "Consent form" },
  { value: "clinical_note_attachment", label: "Clinical note attachment" },
  { value: "other", label: "Other" },
];

const navigationItems = [
  { label: "Overview", path: "" },
  { label: "Chat", path: "chat" },
  { label: "Documents", path: "documents" },
  { label: "Timeline", path: "timeline" },
  { label: "Patient Information", path: "information" },
  { label: "Compare", path: "compare" },
];

const statusStyles = {
  pending_upload: "border-slate-200 bg-slate-50 text-slate-700",
  uploaded: "border-blue-200 bg-blue-50 text-blue-700",
  verified: "border-green-200 bg-green-50 text-green-700",
  processing: "border-amber-200 bg-amber-50 text-amber-700",
  queued: "border-blue-200 bg-blue-50 text-blue-700",
  completed: "border-green-200 bg-green-50 text-green-700",
  partially_completed: "border-blue-200 bg-blue-50 text-blue-700",
  awaiting_ocr: "border-amber-200 bg-amber-50 text-amber-700",
  failed: "border-red-200 bg-red-50 text-red-700",
  archived: "border-slate-200 bg-slate-50 text-slate-600",
  not_started: "border-slate-200 bg-slate-50 text-slate-600",
  extracted: "border-green-200 bg-green-50 text-green-700",
  low_quality_text: "border-amber-200 bg-amber-50 text-amber-700",
  no_text_found: "border-red-200 bg-red-50 text-red-700",
};

export function UploadDocumentPage() {
  const patientId = getPatientId();
  const fileInputRef = useRef(null);
  const [doctor, setDoctor] = useState(() => getStoredDoctor());
  const [patient, setPatient] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState(null);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [documentText, setDocumentText] = useState(null);
  const [documentPages, setDocumentPages] = useState([]);
  const [documentSections, setDocumentSections] = useState([]);
  const [documentArtifacts, setDocumentArtifacts] = useState([]);
  const [documentProcessing, setDocumentProcessing] = useState(null);
  const [reconciliation, setReconciliation] = useState(null);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [documentType, setDocumentType] = useState("lab_report");
  const [documentDate, setDocumentDate] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [duplicateWarning, setDuplicateWarning] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState(null);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  const selectedFileSize = useMemo(() => {
    if (!selectedFile) {
      return "";
    }

    return formatFileSize(selectedFile.size);
  }, [selectedFile]);

  const hasProcessingDocument = documents.some((document) =>
    ["queued", "processing"].includes(document.processing_status),
  );

  useEffect(() => {
    let cancelled = false;

    async function loadPage() {
      setIsLoading(true);
      setError(null);

      try {
        const [doctorData, patientData, documentData, reconciliationData] = await Promise.all([
          getCurrentDoctor(),
          getPatient(patientId),
          listDocuments(patientId, { includeArchived }),
          reconcileDocuments(patientId),
        ]);

        if (cancelled) {
          return;
        }

        setDoctor(doctorData);
        setPatient(patientData);
        setDocuments(documentData.items);
        setReconciliation(reconciliationData);
        setSelectedDocumentId((current) => current ?? documentData.items[0]?.id ?? null);
      } catch (loadError) {
        if (!cancelled) {
          handleRequestError(loadError);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    loadPage();

    return () => {
      cancelled = true;
    };
  }, [patientId, includeArchived]);

  useEffect(() => {
    if (!selectedDocumentId) {
      setSelectedDocument(null);
      setDocumentText(null);
      setDocumentPages([]);
      setDocumentSections([]);
      setDocumentArtifacts([]);
      setDocumentProcessing(null);
      return;
    }

    let cancelled = false;

    async function loadDetails() {
      setDetailsLoading(true);

      try {
        const [processingData, textData, pagesData, sectionsData, artifactsData] =
          await Promise.all([
            getDocumentProcessing(patientId, selectedDocumentId),
            getDocumentText(patientId, selectedDocumentId),
            getDocumentPages(patientId, selectedDocumentId),
            getDocumentSections(patientId, selectedDocumentId),
            getDocumentArtifacts(patientId, selectedDocumentId),
          ]);

        if (cancelled) {
          return;
        }

        setSelectedDocument(processingData.document);
        setDocumentProcessing(processingData);
        setDocumentText(textData);
        setDocumentPages(pagesData);
        setDocumentSections(sectionsData);
        setDocumentArtifacts(artifactsData);
      } catch (detailsError) {
        if (!cancelled) {
          setError(detailsError.message);
        }
      } finally {
        if (!cancelled) {
          setDetailsLoading(false);
        }
      }
    }

    loadDetails();

    return () => {
      cancelled = true;
    };
  }, [patientId, selectedDocumentId]);

  async function reloadDocuments(nextSelectedId = selectedDocumentId) {
    const [documentData, reconciliationData] = await Promise.all([
      listDocuments(patientId, { includeArchived }),
      reconcileDocuments(patientId),
    ]);
    setDocuments(documentData.items);
    setReconciliation(reconciliationData);
    setSelectedDocumentId(nextSelectedId ?? documentData.items[0]?.id ?? null);
  }

  function handleRequestError(requestError) {
    if (requestError.status === 401) {
      clearAuthSession();
      window.location.assign("/");
      return;
    }

    setError(requestError.message);
  }

  function handleFile(file) {
    setError(null);
    setSuccess(null);
    setDuplicateWarning(null);

    if (!file) {
      return;
    }

    const validationError = validateFile(file);

    if (validationError) {
      setSelectedFile(null);
      setError(validationError);
      return;
    }

    const duplicate = documents.find(
      (document) => document.original_filename.toLowerCase() === file.name.toLowerCase(),
    );

    if (duplicate) {
      setDuplicateWarning("A file with this name already exists for this patient.");
    }

    setSelectedFile(file);
    setTitle(suggestTitle(file.name));
  }

  function handleDrop(event) {
    event.preventDefault();
    handleFile(event.dataTransfer.files[0]);
  }

  async function handleUpload(event) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (!selectedFile) {
      setError("Select a PDF, TXT, or DOCX document before uploading.");
      return;
    }

    if (!documentType) {
      setError("Select the document type.");
      return;
    }

    if (!documentDate) {
      setError("Select the document date.");
      return;
    }

    setIsUploading(true);

    try {
      const response = await uploadDocument(patientId, {
        file: selectedFile,
        documentType,
        title: title.trim(),
        description: description.trim(),
        documentDate,
      });

      setSelectedFile(null);
      setDocumentDate("");
      setTitle("");
      setDescription("");
      setDuplicateWarning(response.duplicate_warning ?? null);
      setSuccess("Document uploaded and processing status was saved.");
      cacheCsmDocument(patientId, response.document);
      syncCsm(patientId).catch(() => {});
      await reloadDocuments(response.document.id);
    } catch (uploadError) {
      handleRequestError(uploadError);
    } finally {
      setIsUploading(false);
    }
  }

  function clearFile() {
    setSelectedFile(null);
    setDuplicateWarning(null);
    setError(null);
  }

  async function handleOpenSignedUrl(documentId, mode) {
    setActionLoadingId(`${mode}-${documentId}`);
    setError(null);

    try {
      const result =
        mode === "download"
          ? await getDocumentDownloadUrl(patientId, documentId)
          : await getDocumentViewUrl(patientId, documentId);

      if (mode === "download") {
        const link = window.document.createElement("a");
        link.href = result.signed_url;
        link.rel = "noopener";
        link.click();
      } else {
        window.open(result.signed_url, "_blank", "noopener,noreferrer");
      }
    } catch (urlError) {
      handleRequestError(urlError);
    } finally {
      setActionLoadingId(null);
    }
  }

  async function handleArchiveToggle(document) {
    const action = document.is_active ? archiveDocument : restoreDocument;
    setActionLoadingId(`status-${document.id}`);
    setError(null);
    setSuccess(null);

    try {
      const updatedDocument = await action(patientId, document.id);
      setSuccess(document.is_active ? "Document archived." : "Document restored.");
      await reloadDocuments(updatedDocument.id);
    } catch (statusError) {
      handleRequestError(statusError);
    } finally {
      setActionLoadingId(null);
    }
  }

  async function handleProcess(documentId) {
    setActionLoadingId(`process-${documentId}`);
    setError(null);
    setSuccess(null);

    try {
      await processDocument(patientId, documentId, true);
      setSuccess("Document processing was run again.");
      await reloadDocuments(documentId);
    } catch (processError) {
      handleRequestError(processError);
    } finally {
      setActionLoadingId(null);
    }
  }

  function logout() {
    clearAuthSession();
    window.location.assign("/");
  }

  if (isLoading) {
    return (
      <PageFrame doctor={doctor} patient={patient} patientId={patientId} onLogout={logout}>
        <div className="py-16 text-center text-sm text-slate-600">
          <Loader2 className="mx-auto mb-3 h-5 w-5 animate-spin text-blue-700" />
          Loading patient documents...
        </div>
      </PageFrame>
    );
  }

  return (
    <PageFrame doctor={doctor} patient={patient} patientId={patientId} onLogout={logout}>
      <button
        type="button"
        onClick={() => window.location.assign(`/patients/${patientId}`)}
        className="mb-5 inline-flex items-center gap-2 rounded text-sm font-medium text-slate-600 transition hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-blue-100"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to patient overview
      </button>

      <Breadcrumb patient={patient} patientId={patientId} />

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">
              {patient?.full_name ?? "Patient"} - {patient?.patient_code ?? patientId}
            </p>
            <h1 className="mt-2 text-2xl font-semibold text-slate-950">
              Patient Documents
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              Upload and manage patient-specific records stored in private object storage.
            </p>
            <p className="mt-3 text-sm text-slate-600">
              {formatPatientSummary(patient)}
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={() => setIncludeArchived((current) => !current)}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
            >
              {includeArchived ? <RotateCcw className="h-4 w-4" /> : <Archive className="h-4 w-4" />}
              {includeArchived ? "Hide Archived" : "Show Archived"}
            </button>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200"
            >
              <Upload className="h-4 w-4" aria-hidden="true" />
              Upload Document
            </button>
          </div>
        </div>
      </section>

      <PatientNav patientId={patientId} />

      <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <form onSubmit={handleUpload} className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-6 py-4">
            <h2 className="text-base font-semibold text-slate-950">
              Upload Medical Document
            </h2>
          </div>

          <div className="space-y-5 p-6">
            <FileDropZone
              fileInputRef={fileInputRef}
              selectedFile={selectedFile}
              selectedFileSize={selectedFileSize}
              onFile={handleFile}
              onDrop={handleDrop}
              onClear={clearFile}
            />

            <div className="grid gap-5 sm:grid-cols-2">
              <FormField label="Document type" htmlFor="document-type">
                <select
                  id="document-type"
                  value={documentType}
                  onChange={(event) => setDocumentType(event.target.value)}
                  className={inputClass()}
                >
                  {documentTypes.map((type) => (
                    <option key={type.value} value={type.value}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </FormField>

              <FormField label="Document date" htmlFor="document-date">
                <input
                  id="document-date"
                  type="date"
                  value={documentDate}
                  max={new Date().toISOString().split("T")[0]}
                  onChange={(event) => setDocumentDate(event.target.value)}
                  className={inputClass()}
                />
              </FormField>
            </div>

            <FormField label="Title" htmlFor="document-title">
              <input
                id="document-title"
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Blood Test Report - July 2026"
                className={inputClass()}
              />
            </FormField>

            <FormField label="Description" htmlFor="document-description">
              <textarea
                id="document-description"
                rows={4}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Optional context about this document"
                className={`${inputClass()} h-auto resize-y py-3`}
              />
            </FormField>

            {duplicateWarning ? <Notice tone="warning" message={duplicateWarning} /> : null}
            {success ? <Notice tone="success" message={success} /> : null}
            {error ? <Notice tone="error" message={error} /> : null}
          </div>

          <footer className="flex flex-col-reverse gap-3 border-t border-slate-200 bg-slate-50 px-6 py-4 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={() => window.location.assign(`/patients/${patientId}`)}
              disabled={isUploading}
              className="inline-flex h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 focus:outline-none focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isUploading}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-blue-700 px-5 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isUploading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4" aria-hidden="true" />
                  Upload Document
                </>
              )}
            </button>
          </footer>
        </form>

        <ProcessingPanel
          selectedDocument={selectedDocument}
          documentProcessing={documentProcessing}
          reconciliation={reconciliation}
          showTechnicalDetails={showTechnicalDetails}
          setShowTechnicalDetails={setShowTechnicalDetails}
          hasProcessingDocument={hasProcessingDocument || isUploading}
        />
      </section>

      <DocumentsSection
        documents={documents}
        patientId={patientId}
        selectedDocumentId={selectedDocumentId}
        actionLoadingId={actionLoadingId}
        onSelect={setSelectedDocumentId}
        onView={(documentId) => handleOpenSignedUrl(documentId, "view")}
        onDownload={(documentId) => handleOpenSignedUrl(documentId, "download")}
        onArchiveToggle={handleArchiveToggle}
        onProcess={handleProcess}
      />

      <DocumentDetailsPanel
        document={selectedDocument}
        text={documentText}
        pages={documentPages}
        sections={documentSections}
        artifacts={documentArtifacts}
        processing={documentProcessing}
        loading={detailsLoading}
      />
    </PageFrame>
  );
}

function PageFrame({ doctor, patient, patientId, onLogout, children }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8">
          <button
            type="button"
            onClick={() => window.location.assign(`/patients/${patientId}`)}
            className="flex items-center gap-3 rounded-lg focus:outline-none focus:ring-4 focus:ring-blue-100"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-700 text-white">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="hidden text-left sm:block">
              <p className="text-sm font-semibold text-slate-950">
                Medical Memory Platform
              </p>
              <p className="text-xs text-slate-500">
                {patient?.full_name ? `${patient.full_name} documents` : "Patient documents"}
              </p>
            </div>
          </button>

          <div className="flex items-center gap-2 sm:gap-4">
            <button
              type="button"
              className="hidden h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100 sm:flex"
            >
              <UserRound className="h-4 w-4" aria-hidden="true" />
              {doctor?.full_name ?? "Doctor"}
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
            </button>

            <button
              type="button"
              onClick={onLogout}
              className="flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8">{children}</main>
    </div>
  );
}

function Breadcrumb({ patient, patientId }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-5 flex items-center gap-2 text-sm text-slate-500">
      <button
        type="button"
        onClick={() => window.location.assign("/patients")}
        className="rounded transition hover:text-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-100"
      >
        Patients
      </button>
      <span aria-hidden="true">/</span>
      <button
        type="button"
        onClick={() => window.location.assign(`/patients/${patientId}`)}
        className="rounded transition hover:text-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-100"
      >
        {patient?.full_name ?? "Patient"}
      </button>
      <span aria-hidden="true">/</span>
      <span className="font-medium text-slate-700">Documents</span>
    </nav>
  );
}

function PatientNav({ patientId }) {
  return (
    <nav className="mt-6 overflow-x-auto border-b border-slate-200">
      <div className="flex min-w-max gap-1">
        {navigationItems.map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={() => {
              const suffix = item.path ? `/${item.path}` : "";
              window.location.assign(`/patients/${patientId}${suffix}`);
            }}
            className={`h-11 whitespace-nowrap border-b-2 px-4 text-sm font-medium ${
              item.label === "Documents"
                ? "border-blue-700 text-blue-700"
                : "border-transparent text-slate-600 hover:text-slate-950"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>
    </nav>
  );
}

function FileDropZone({
  fileInputRef,
  selectedFile,
  selectedFileSize,
  onFile,
  onDrop,
  onClear,
}) {
  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-slate-700">
        Document file
      </label>

      <div
        onDragOver={(event) => event.preventDefault()}
        onDrop={onDrop}
        className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-8 text-center"
      >
        <FolderOpen className="mx-auto h-9 w-9 text-slate-400" />
        <p className="mt-3 text-sm font-medium text-slate-800">
          Drag and drop a medical document here
        </p>
        <p className="mt-1 text-xs text-slate-500">
          Supported: PDF, TXT, DOCX. Maximum size: 20 MB.
        </p>

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="mt-4 inline-flex h-10 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
        >
          Browse files
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.docx,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          className="hidden"
          onChange={(event) => onFile(event.target.files[0])}
        />
      </div>

      {selectedFile ? (
        <div className="mt-3 flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white px-4 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <FileText className="h-5 w-5 shrink-0 text-blue-700" aria-hidden="true" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-950">
                {selectedFile.name}
              </p>
              <p className="text-xs text-slate-500">
                {fileTypeLabel(selectedFile)} - {selectedFileSize}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClear}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-4 focus:ring-blue-100"
            aria-label="Remove selected file"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      ) : null}
    </div>
  );
}

function ProcessingPanel({
  selectedDocument,
  documentProcessing,
  reconciliation,
  showTechnicalDetails,
  setShowTechnicalDetails,
  hasProcessingDocument,
}) {
  const stages = buildProcessingStages(selectedDocument, hasProcessingDocument);
  const latestJob = documentProcessing?.jobs?.[0] ?? null;

  return (
    <aside className="rounded-xl border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-base font-semibold text-slate-950">
          Processing Status
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Current document lifecycle and extraction status.
        </p>
      </div>

      <div className="space-y-3 p-5">
        {stages.map((stage) => (
          <div key={stage.label} className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              {stageIcon(stage.status)}
              <span className="text-sm font-medium text-slate-700">{stage.label}</span>
            </div>
            <StatusBadge status={stage.status} />
          </div>
        ))}

        {latestJob ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            Latest job: {formatStatus(latestJob.status)} on attempt {latestJob.attempt_number}
          </div>
        ) : null}

        {reconciliation?.total ? (
          <Notice
            tone="warning"
            message={`${reconciliation.total} document storage issue${reconciliation.total === 1 ? "" : "s"} found.`}
          />
        ) : null}

        <button
          type="button"
          onClick={() => setShowTechnicalDetails((current) => !current)}
          className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-blue-700 hover:text-blue-800"
        >
          {showTechnicalDetails ? "Hide" : "View"} technical details
          <ChevronDown className="h-4 w-4" aria-hidden="true" />
        </button>

        {showTechnicalDetails ? (
          <div className="mt-3 space-y-3 border-t border-slate-200 pt-4">
            <TechnicalRow label="Upload" value={selectedDocument?.upload_status} />
            <TechnicalRow label="Verification" value={selectedDocument?.verification_status} />
            <TechnicalRow label="Text extraction" value={selectedDocument?.text_extraction_status} />
            <TechnicalRow label="OCR requirement" value={selectedDocument?.ocr_requirement_status} />
            <TechnicalRow label="Artifacts" value={selectedDocument?.artifact_count ?? 0} />
            <TechnicalRow label="Pages" value={selectedDocument?.page_count ?? 0} />
          </div>
        ) : null}
      </div>
    </aside>
  );
}

function DocumentsSection({
  documents,
  selectedDocumentId,
  actionLoadingId,
  onSelect,
  onView,
  onDownload,
  onArchiveToggle,
  onProcess,
}) {
  return (
    <section className="mt-8 rounded-xl border border-slate-200 bg-white">
      <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-950">
            Existing Documents
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Uploaded source files remain private and are opened through short-lived links.
          </p>
        </div>
      </div>

      {documents.length === 0 ? (
        <EmptyDocuments />
      ) : (
        <>
          <div className="hidden overflow-x-auto lg:block">
            <table className="min-w-full">
              <thead className="bg-slate-50">
                <tr>
                  <TableHeader>Document</TableHeader>
                  <TableHeader>Type</TableHeader>
                  <TableHeader>Document date</TableHeader>
                  <TableHeader>Uploaded</TableHeader>
                  <TableHeader>Status</TableHeader>
                  <TableHeader>Size</TableHeader>
                  <TableHeader>Actions</TableHeader>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {documents.map((document) => (
                  <tr
                    key={document.id}
                    className={document.id === selectedDocumentId ? "bg-blue-50/50" : "bg-white"}
                  >
                    <TableCell>
                      <button
                        type="button"
                        onClick={() => onSelect(document.id)}
                        className="max-w-xs text-left"
                      >
                        <p className="truncate text-sm font-semibold text-slate-950">
                          {document.title || suggestTitle(document.original_filename)}
                        </p>
                        <p className="mt-1 truncate text-xs text-slate-500">
                          {document.original_filename}
                        </p>
                      </button>
                    </TableCell>
                    <TableCell>{formatType(document.document_type)}</TableCell>
                    <TableCell>{formatDateText(document.document_date)}</TableCell>
                    <TableCell>{formatDateTime(document.uploaded_at)}</TableCell>
                    <TableCell>
                      <StatusBadge
                        status={document.is_active ? document.processing_status : "archived"}
                      />
                    </TableCell>
                    <TableCell>{formatFileSize(document.size_bytes_actual ?? document.size_bytes_expected)}</TableCell>
                    <TableCell>
                      <DocumentActions
                        document={document}
                        actionLoadingId={actionLoadingId}
                        onView={onView}
                        onDownload={onDownload}
                        onArchiveToggle={onArchiveToggle}
                        onProcess={onProcess}
                      />
                    </TableCell>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="divide-y divide-slate-200 lg:hidden">
            {documents.map((document) => (
              <div key={document.id} className="p-5">
                <button type="button" onClick={() => onSelect(document.id)} className="w-full text-left">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-slate-950">
                        {document.title || suggestTitle(document.original_filename)}
                      </p>
                      <p className="mt-1 truncate text-xs text-slate-500">
                        {document.original_filename}
                      </p>
                    </div>
                    <StatusBadge status={document.is_active ? document.processing_status : "archived"} />
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-3 text-sm text-slate-600">
                    <InfoPair label="Type" value={formatType(document.document_type)} />
                    <InfoPair label="Size" value={formatFileSize(document.size_bytes_actual ?? document.size_bytes_expected)} />
                    <InfoPair label="Date" value={formatDateText(document.document_date)} />
                    <InfoPair label="Uploaded" value={formatDateTime(document.uploaded_at)} />
                  </div>
                </button>
                <div className="mt-4">
                  <DocumentActions
                    document={document}
                    actionLoadingId={actionLoadingId}
                    onView={onView}
                    onDownload={onDownload}
                    onArchiveToggle={onArchiveToggle}
                    onProcess={onProcess}
                  />
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function DocumentDetailsPanel({
  document,
  text,
  pages,
  sections,
  artifacts,
  processing,
  loading,
}) {
  if (!document && !loading) {
    return null;
  }

  return (
    <section className="mt-8 rounded-xl border border-slate-200 bg-white">
      <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-950">
            Document Details
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Processing output, extracted text, pages, sections, and generated artifacts.
          </p>
        </div>
        {document ? <StatusBadge status={document.processing_status} /> : null}
      </div>

      {loading ? (
        <div className="py-12 text-center text-sm text-slate-600">
          <Loader2 className="mx-auto mb-3 h-5 w-5 animate-spin text-blue-700" />
          Loading document details...
        </div>
      ) : (
        <div className="grid gap-6 p-5 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-semibold text-slate-950">
                {document.title || suggestTitle(document.original_filename)}
              </h3>
              <p className="mt-1 text-sm text-slate-600">{document.description || "No description added."}</p>
            </div>

            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <h3 className="text-sm font-semibold text-slate-950">Extracted Text</h3>
              <p className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap text-sm leading-6 text-slate-700">
                {text?.normalized_text || "No extracted text available yet."}
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <OutputList title="Pages" items={pages} emptyText="No pages saved." renderItem={(page) => (
                <div>
                  <p className="text-sm font-semibold text-slate-950">Page {page.page_number}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {page.character_count} characters, {page.word_count} words
                  </p>
                  <p className="mt-2 line-clamp-3 text-sm text-slate-600">
                    {page.normalized_text || "No text on this page."}
                  </p>
                </div>
              )} />
              <OutputList title="Sections" items={sections} emptyText="No sections saved." renderItem={(section) => (
                <div>
                  <p className="text-sm font-semibold text-slate-950">
                    {section.heading || `Section ${section.section_index}`}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {section.section_type || "section"} · {section.normalized_text.length} characters
                  </p>
                  <p className="mt-2 line-clamp-3 text-sm text-slate-600">
                    {section.normalized_text}
                  </p>
                </div>
              )} />
            </div>
          </div>

          <aside className="space-y-4">
            <DetailGrid document={document} text={text} processing={processing} />
            <OutputList
              title="Artifacts"
              items={artifacts}
              emptyText="No artifacts saved."
              renderItem={(artifact) => (
                <div>
                  <p className="text-sm font-semibold text-slate-950">
                    {formatType(artifact.artifact_type)}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {artifact.content_type} · {formatFileSize(artifact.size_bytes ?? 0)}
                  </p>
                </div>
              )}
            />
          </aside>
        </div>
      )}
    </section>
  );
}

function DocumentActions({
  document,
  actionLoadingId,
  onView,
  onDownload,
  onArchiveToggle,
  onProcess,
}) {
  const canOpen = document.upload_status === "uploaded" && document.verification_status === "verified";

  return (
    <div className="flex flex-wrap gap-2">
      <ActionButton
        label="View"
        icon={<FileText className="h-4 w-4" />}
        disabled={!canOpen}
        loading={actionLoadingId === `view-${document.id}`}
        onClick={() => onView(document.id)}
      />
      <ActionButton
        label="Download"
        icon={<Download className="h-4 w-4" />}
        disabled={!canOpen}
        loading={actionLoadingId === `download-${document.id}`}
        onClick={() => onDownload(document.id)}
      />
      <ActionButton
        label="Retry"
        icon={<RefreshCcw className="h-4 w-4" />}
        disabled={!canOpen || ["queued", "processing"].includes(document.processing_status)}
        loading={actionLoadingId === `process-${document.id}`}
        onClick={() => onProcess(document.id)}
      />
      <ActionButton
        label={document.is_active ? "Archive" : "Restore"}
        icon={document.is_active ? <Archive className="h-4 w-4" /> : <RotateCcw className="h-4 w-4" />}
        loading={actionLoadingId === `status-${document.id}`}
        onClick={() => onArchiveToggle(document)}
      />
    </div>
  );
}

function ActionButton({ label, icon, disabled, loading, onClick }) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      onClick={onClick}
      className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {label}
    </button>
  );
}

function DetailGrid({ document, text, processing }) {
  const latestJob = processing?.jobs?.[0];

  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <h3 className="text-sm font-semibold text-slate-950">Metadata</h3>
      <div className="mt-4 space-y-3">
        <InfoPair label="File" value={document.original_filename} />
        <InfoPair label="Type" value={formatType(document.document_type)} />
        <InfoPair label="Uploaded" value={formatDateTime(document.uploaded_at)} />
        <InfoPair label="Verified" value={formatDateTime(document.verified_at)} />
        <InfoPair label="Extraction" value={formatStatus(document.text_extraction_status)} />
        <InfoPair label="OCR" value={formatStatus(document.ocr_requirement_status)} />
        <InfoPair label="Quality" value={formatStatus(text?.quality_status)} />
        <InfoPair label="Words" value={text?.word_count ?? 0} />
        <InfoPair label="Latest job" value={formatStatus(latestJob?.status)} />
      </div>
    </div>
  );
}

function OutputList({ title, items, emptyText, renderItem }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-950">{title}</h3>
      </div>
      {items.length ? (
        <div className="max-h-80 divide-y divide-slate-200 overflow-auto">
          {items.map((item, index) => (
            <div key={item.id ?? index} className="p-4">
              {renderItem(item)}
            </div>
          ))}
        </div>
      ) : (
        <p className="p-4 text-sm text-slate-500">{emptyText}</p>
      )}
    </div>
  );
}

function EmptyDocuments() {
  return (
    <div className="px-5 py-12 text-center">
      <FileText className="mx-auto h-10 w-10 text-slate-300" />
      <h3 className="mt-4 text-sm font-semibold text-slate-950">
        No documents uploaded
      </h3>
      <p className="mt-1 text-sm text-slate-500">
        Upload a medical document to begin building this patient's evidence memory.
      </p>
    </div>
  );
}

function Notice({ tone, message }) {
  const styles = {
    success: "border-green-200 bg-green-50 text-green-700",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    error: "border-red-200 bg-red-50 text-red-700",
    info: "border-blue-200 bg-blue-50 text-blue-700",
  };
  const Icon = tone === "success" ? CheckCircle2 : tone === "info" ? Info : AlertCircle;

  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${styles[tone] ?? styles.info}`}>
      <div className="flex gap-2">
        <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <span>{message}</span>
      </div>
    </div>
  );
}

function FormField({ label, htmlFor, children }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </label>
      {children}
    </div>
  );
}

function TableHeader({ children }) {
  return (
    <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
      {children}
    </th>
  );
}

function TableCell({ children }) {
  return <td className="px-5 py-4 align-top text-sm text-slate-600">{children}</td>;
}

function InfoPair({ label, value }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 break-words text-sm font-medium text-slate-700">{value || "Not set"}</p>
    </div>
  );
}

function TechnicalRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-slate-600">{label}</span>
      <span className="text-sm font-semibold text-slate-800">
        {typeof value === "number" ? value : formatStatus(value)}
      </span>
    </div>
  );
}

function StatusBadge({ status }) {
  const normalizedStatus = status || "not_started";

  return (
    <span
      className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${statusStyles[normalizedStatus] ?? "border-slate-200 bg-slate-50 text-slate-700"}`}
    >
      {formatStatus(normalizedStatus)}
    </span>
  );
}

function stageIcon(status) {
  if (["completed", "verified", "uploaded", "extracted"].includes(status)) {
    return <CheckCircle2 className="h-4 w-4 text-green-600" aria-hidden="true" />;
  }

  if (["processing", "queued"].includes(status)) {
    return <Loader2 className="h-4 w-4 animate-spin text-amber-600" aria-hidden="true" />;
  }

  if (status === "failed") {
    return <AlertCircle className="h-4 w-4 text-red-600" aria-hidden="true" />;
  }

  return <div className="h-2.5 w-2.5 rounded-full bg-slate-300" />;
}

function buildProcessingStages(document, fallbackProcessing) {
  if (!document) {
    return [
      { label: "File uploaded", status: fallbackProcessing ? "processing" : "not_started" },
      { label: "Upload verified", status: "not_started" },
      { label: "Text extracted", status: "not_started" },
      { label: "OCR checked", status: "not_started" },
      { label: "Ready for questions", status: "not_started" },
    ];
  }

  return [
    { label: "File uploaded", status: document.upload_status },
    { label: "Upload verified", status: document.verification_status },
    { label: "Text extracted", status: document.text_extraction_status },
    { label: "OCR checked", status: document.ocr_requirement_status },
    { label: "Ready for questions", status: document.processing_status },
  ];
}

function getPatientId() {
  return window.location.pathname.split("/")[2] || "";
}

function validateFile(file) {
  const extension = file.name.toLowerCase().split(".").pop();
  const knownByType = Boolean(allowedTypes[file.type]);
  const knownByExtension = ["pdf", "txt", "docx"].includes(extension);

  if (!knownByType && !knownByExtension) {
    return "This file type is not supported.";
  }

  if (file.size === 0) {
    return "The document could not be read.";
  }

  if (file.size > maxFileSize) {
    return "The file exceeds the 20 MB limit.";
  }

  return null;
}

function fileTypeLabel(file) {
  if (allowedTypes[file.type]) {
    return allowedTypes[file.type];
  }

  return file.name.split(".").pop()?.toUpperCase() || "Document";
}

function inputClass() {
  return "h-11 w-full rounded-lg border border-slate-300 bg-white px-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-700 focus:ring-4 focus:ring-blue-100";
}

function suggestTitle(filename = "") {
  return filename
    .replace(/\.[^/.]+$/, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatPatientSummary(patient) {
  if (!patient) {
    return "Patient record loading";
  }

  const parts = [];

  if (patient.date_of_birth) {
    parts.push(`${calculateAge(patient.date_of_birth)} years`);
  }

  if (patient.sex) {
    parts.push(formatStatus(patient.sex));
  }

  if (patient.phone) {
    parts.push(patient.phone);
  }

  return parts.length ? parts.join(", ") : "No demographics added";
}

function calculateAge(dateOfBirth) {
  const birthDate = new Date(`${dateOfBirth}T00:00:00`);
  const today = new Date();
  let age = today.getFullYear() - birthDate.getFullYear();
  const monthDelta = today.getMonth() - birthDate.getMonth();

  if (monthDelta < 0 || (monthDelta === 0 && today.getDate() < birthDate.getDate())) {
    age -= 1;
  }

  return age;
}

function formatType(value = "") {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatStatus(value = "") {
  if (!value) {
    return "Not set";
  }

  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatFileSize(size) {
  if (!size) {
    return "0 KB";
  }

  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }

  return `${Math.max(1, Math.round(size / 1024))} KB`;
}

function formatDateText(value) {
  if (!value) {
    return "Not set";
  }

  const date = new Date(`${value}T00:00:00`);

  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatDateTime(value) {
  if (!value) {
    return "Not set";
  }

  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
