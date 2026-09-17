import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  ArrowLeft,
  Download,
  FileText,
  Loader2,
  RefreshCcw,
  Search,
  ShieldCheck,
  Upload,
} from "lucide-react";

import { getPatient } from "../patient_shared/patientApi";
import {
  archiveDocument,
  getDocument,
  getDocumentArtifacts,
  getDocumentDownloadUrl,
  getDocumentPages,
  getDocumentProcessing,
  getDocumentSections,
  getDocumentText,
  getDocumentViewUrl,
  processDocument,
  restoreDocument,
} from "../upload_document/documentApi";

export function MedicalDocumentViewerPage() {
  const patientId = getPatientId();
  const documentId = getDocumentId();
  const query = new URLSearchParams(window.location.search);
  const [patient, setPatient] = useState(null);
  const [document, setDocument] = useState(null);
  const [processing, setProcessing] = useState(null);
  const [text, setText] = useState(null);
  const [pages, setPages] = useState([]);
  const [sections, setSections] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [activeTab, setActiveTab] = useState("Text");
  const [pageNumber, setPageNumber] = useState(Number(query.get("page")) || 1);
  const [searchTerm, setSearchTerm] = useState(query.get("highlight") || "");
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const currentPage = pages.find((page) => page.page_number === pageNumber) ?? pages[0] ?? null;
  const visibleSections = useMemo(() => {
    const queryText = searchTerm.trim().toLowerCase();

    if (!queryText) {
      return sections;
    }

    return sections.filter((section) =>
      [section.heading, section.section_type, section.normalized_text]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(queryText),
    );
  }, [sections, searchTerm]);
  const searchMatches = useMemo(() => {
    const queryText = searchTerm.trim().toLowerCase();

    if (!queryText) {
      return [];
    }

    return pages.filter((page) => page.normalized_text.toLowerCase().includes(queryText));
  }, [pages, searchTerm]);

  useEffect(() => {
    load();
  }, [patientId, documentId]);

  async function load() {
    setLoading(true);
    setError(null);

    try {
      const [
        patientData,
        documentData,
        processingData,
        textData,
        pageData,
        sectionData,
        artifactData,
      ] = await Promise.all([
        getPatient(patientId),
        getDocument(patientId, documentId),
        getDocumentProcessing(patientId, documentId),
        getDocumentText(patientId, documentId),
        getDocumentPages(patientId, documentId),
        getDocumentSections(patientId, documentId),
        getDocumentArtifacts(patientId, documentId),
      ]);
      setPatient(patientData);
      setDocument(documentData);
      setProcessing(processingData);
      setText(textData);
      setPages(pageData);
      setSections(sectionData);
      setArtifacts(artifactData);
      setPageNumber((current) => clampPage(current, pageData.length || documentData.page_count || 1));
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  async function runAction(label, handler) {
    setAction(label);
    setError(null);
    setSuccess(null);

    try {
      await handler();
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setAction(null);
    }
  }

  async function openSignedUrl(type) {
    await runAction(type, async () => {
      const result =
        type === "view"
          ? await getDocumentViewUrl(patientId, documentId)
          : await getDocumentDownloadUrl(patientId, documentId);
      window.open(result.signed_url, "_blank", "noopener,noreferrer");
    });
  }

  async function retryProcessing() {
    await runAction("process", async () => {
      await processDocument(patientId, documentId, true);
      setSuccess("Document processing completed.");
      await load();
    });
  }

  async function toggleArchive() {
    await runAction("archive", async () => {
      if (document?.is_active) {
        await archiveDocument(patientId, documentId);
        setSuccess("Document archived.");
      } else {
        await restoreDocument(patientId, documentId);
        setSuccess("Document restored.");
      }

      await load();
    });
  }

  if (loading) {
    return <DocumentShell patient={patient} patientId={patientId}>Loading document...</DocumentShell>;
  }

  if (!document) {
    return (
      <DocumentShell patient={patient} patientId={patientId}>
        <NoDocumentState patientId={patientId} error={error} />
      </DocumentShell>
    );
  }

  return (
    <DocumentShell patient={patient} patientId={patientId}>
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-sm font-medium text-slate-500">
              {patient?.full_name ?? "Patient"} - {patient?.patient_code ?? patientId}
            </p>
            <h1 className="mt-2 break-words text-2xl font-semibold text-slate-950">
              {document.title || document.original_filename}
            </h1>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {formatType(document.document_type)} - {document.original_filename}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <ActionButton label="View" icon={<FileText className="h-4 w-4" />} loading={action === "view"} onClick={() => openSignedUrl("view")} />
            <ActionButton label="Download" icon={<Download className="h-4 w-4" />} loading={action === "download"} onClick={() => openSignedUrl("download")} />
            <ActionButton label="Process" icon={<RefreshCcw className="h-4 w-4" />} loading={action === "process"} onClick={retryProcessing} />
            <ActionButton label={document.is_active ? "Archive" : "Restore"} icon={<Archive className="h-4 w-4" />} loading={action === "archive"} onClick={toggleArchive} />
          </div>
        </div>
      </section>

      {error ? <Notice tone="error" message={error} /> : null}
      {success ? <Notice tone="success" message={success} /> : null}

      <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Processing" value={formatType(document.processing_status)} />
        <Metric label="Extraction" value={formatType(document.text_extraction_status)} />
        <Metric label="Pages" value={document.page_count || pages.length} />
        <Metric label="Sections" value={document.section_count || sections.length} />
        <Metric label="Artifacts" value={document.artifact_count || artifacts.length} />
      </section>

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-4">
        <label className="relative block">
          <Search className="pointer-events-none absolute left-3 top-3.5 h-4 w-4 text-slate-400" />
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search extracted text"
            className="h-11 w-full rounded-lg border border-slate-300 pl-9 pr-28 text-sm outline-none focus:border-blue-700 focus:ring-4 focus:ring-blue-100"
          />
          {searchTerm ? (
            <span className="absolute right-3 top-3.5 text-xs text-slate-500">
              {searchMatches.length} page matches
            </span>
          ) : null}
        </label>
      </section>

      <section className="mt-6 grid gap-6 xl:grid-cols-[260px_minmax(0,1fr)_360px]">
        <Panel title="Pages" icon={<FileText className="h-4 w-4" />}>
          <div className="max-h-[560px] space-y-2 overflow-auto">
            {pages.map((page) => (
              <button
                key={page.id}
                type="button"
                onClick={() => setPageNumber(page.page_number)}
                className={`w-full rounded-lg border px-3 py-3 text-left text-sm transition ${
                  page.page_number === pageNumber
                    ? "border-blue-300 bg-blue-50 text-blue-900"
                    : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                }`}
              >
                <span className="block font-semibold">Page {page.page_number}</span>
                <span className="mt-1 line-clamp-2 block text-xs text-slate-500">
                  {page.normalized_text || "No extracted text"}
                </span>
              </button>
            ))}
            {!pages.length ? <EmptyPanelText text="No page-level text was extracted." /> : null}
          </div>
        </Panel>

        <Panel title="Extracted Content" icon={<FileText className="h-4 w-4" />}>
          <div className="flex flex-wrap gap-2">
            {["Text", "Page", "Sections"].map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveTab(tab)}
                className={`h-9 rounded-lg px-3 text-sm font-semibold ${
                  activeTab === tab
                    ? "bg-blue-700 text-white"
                    : "border border-slate-300 bg-white text-slate-700"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="mt-5 min-h-[520px] rounded-lg border border-slate-200 bg-slate-50 p-4">
            {activeTab === "Text" ? (
              <TextBlock text={text?.normalized_text} emptyText="No full-document text is available." />
            ) : null}

            {activeTab === "Page" ? (
              <TextBlock text={currentPage?.normalized_text} emptyText="No text is available for this page." />
            ) : null}

            {activeTab === "Sections" ? (
              <div className="space-y-3">
                {visibleSections.map((section) => (
                  <article key={section.id} className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h3 className="font-semibold text-slate-950">
                        {section.heading || `Section ${section.section_index + 1}`}
                      </h3>
                      <span className="text-xs text-slate-500">
                        {formatType(section.section_type)} - pages {section.page_start ?? "n/a"}-{section.page_end ?? "n/a"}
                      </span>
                    </div>
                    <p className="mt-3 whitespace-pre-wrap leading-6 text-slate-700">{section.normalized_text}</p>
                  </article>
                ))}
                {!visibleSections.length ? <EmptyPanelText text="No matching sections found." /> : null}
              </div>
            ) : null}
          </div>
        </Panel>

        <aside className="space-y-6">
          <Panel title="Metadata" icon={<FileText className="h-4 w-4" />}>
            <dl className="space-y-3 text-sm">
              <InfoRow label="Status" value={formatType(document.upload_status)} />
              <InfoRow label="Verification" value={formatType(document.verification_status)} />
              <InfoRow label="Active" value={document.is_active ? "Yes" : "No"} />
              <InfoRow label="Current version" value={document.is_current_version ? "Yes" : "No"} />
              <InfoRow label="Version" value={document.version_number} />
              <InfoRow label="Document date" value={formatDate(document.document_date)} />
              <InfoRow label="Uploaded" value={formatDateTime(document.uploaded_at)} />
              <InfoRow label="Size" value={formatBytes(document.size_bytes_actual ?? document.size_bytes_expected)} />
              <InfoRow label="Content type" value={document.detected_content_type ?? document.declared_content_type} />
            </dl>
          </Panel>

          <Panel title="Processing Jobs" icon={<RefreshCcw className="h-4 w-4" />}>
            <div className="space-y-3">
              {processing?.jobs?.map((job) => (
                <article key={job.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <StatusBadge label={formatType(job.status)} />
                    <span className="text-xs text-slate-500">Attempt {job.attempt_number}/{job.max_attempts}</span>
                  </div>
                  <p className="mt-2 font-medium text-slate-800">{formatType(job.job_type)}</p>
                  <p className="mt-1 text-xs text-slate-500">
                    {job.processor_name} v{job.processor_version}
                  </p>
                  {job.failure_reason ? <p className="mt-2 text-xs text-red-700">{job.failure_reason}</p> : null}
                </article>
              ))}
              {!processing?.jobs?.length ? <EmptyPanelText text="No processing jobs found." /> : null}
            </div>
          </Panel>

          <Panel title="Artifacts" icon={<FileText className="h-4 w-4" />}>
            <div className="space-y-3">
              {artifacts.map((artifact) => (
                <article key={artifact.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                  <p className="font-semibold text-slate-950">{formatType(artifact.artifact_type)}</p>
                  <p className="mt-1 text-xs text-slate-500">{artifact.content_type}</p>
                  <p className="mt-1 text-xs text-slate-500">{formatBytes(artifact.size_bytes)}</p>
                </article>
              ))}
              {!artifacts.length ? <EmptyPanelText text="No generated artifacts found." /> : null}
            </div>
          </Panel>
        </aside>
      </section>
    </DocumentShell>
  );
}

function DocumentShell({ patient, patientId, children }) {
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
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="hidden text-left sm:block">
              <p className="text-sm font-semibold text-slate-950">Medical Memory Platform</p>
              <p className="text-xs text-slate-500">{patient?.full_name ?? "Document viewer"}</p>
            </div>
          </button>
          <button
            type="button"
            onClick={() => window.location.assign(`/patients/${patientId}/documents`)}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Documents
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8">{children}</main>
    </div>
  );
}

function NoDocumentState({ patientId, error }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-8 text-center shadow-clinical">
      <FileText className="mx-auto h-10 w-10 text-slate-400" />
      <h1 className="mt-4 text-lg font-semibold text-slate-950">No document found</h1>
      <p className="mt-2 text-sm text-slate-600">
        {error || "Upload a document for this patient to inspect extracted text and processing status."}
      </p>
      <button
        type="button"
        onClick={() => window.location.assign(`/patients/${patientId}/documents`)}
        className="mt-5 inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white"
      >
        <Upload className="h-4 w-4" />
        Upload Document
      </button>
    </section>
  );
}

function Panel({ title, icon, children }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-4">
        {icon}
        <h2 className="text-base font-semibold text-slate-950">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function ActionButton({ label, icon, loading, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {label}
    </button>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-slate-950">{value ?? "Not set"}</p>
    </div>
  );
}

function TextBlock({ text, emptyText }) {
  if (!text) {
    return <EmptyPanelText text={emptyText} />;
  }

  return <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">{text}</p>;
}

function EmptyPanelText({ text }) {
  return <p className="rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-500">{text}</p>;
}

function Notice({ tone, message }) {
  const classes =
    tone === "success"
      ? "border-green-200 bg-green-50 text-green-700"
      : "border-red-200 bg-red-50 text-red-700";

  return <div className={`mt-6 rounded-lg border px-4 py-3 text-sm ${classes}`}>{message}</div>;
}

function StatusBadge({ label }) {
  return (
    <span className="inline-flex rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
      {label}
    </span>
  );
}

function InfoRow({ label, value }) {
  const displayValue =
    value === null || value === undefined || value === "" ? "Not set" : value;

  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="break-words text-right font-medium text-slate-800">{displayValue}</dd>
    </div>
  );
}

function formatType(value = "") {
  if (value === null || value === undefined || value === "") {
    return "Not set";
  }

  return String(value).replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value) {
  if (!value) {
    return "Not set";
  }

  return new Date(value).toLocaleDateString("en-IN", {
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

function formatBytes(value) {
  if (!value && value !== 0) {
    return "Not set";
  }

  if (value < 1024) {
    return `${value} B`;
  }

  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }

  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function clampPage(pageNumber, pageCount) {
  return Math.min(Math.max(pageNumber, 1), Math.max(pageCount, 1));
}

function getPatientId() {
  return window.location.pathname.split("/")[2] || "";
}

function getDocumentId() {
  return window.location.pathname.split("/")[4] || "";
}
