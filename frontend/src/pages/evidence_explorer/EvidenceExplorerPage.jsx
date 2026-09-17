import { useEffect, useMemo, useState } from "react";
import {
  BookOpenText,
  Download,
  FileText,
  GitBranch,
  Search,
} from "lucide-react";
import {
  BackButton,
  Drawer,
  EmptyState,
  InfoRow,
  PageHero,
  PatientBanner,
  PlatformShell,
  PrimaryButton,
  SecondaryButton,
  SelectField,
  StatePanel,
  StatusBadge,
  TableShell,
  getPatientId,
  go,
  inputClass,
  platformPatient,
} from "../platform_shared/PlatformShell";
import {
  buildEvidenceRelationships,
  fetchPatientEvidence,
} from "./evidenceExplorerService";

export function EvidenceExplorerPage() {
  const patientId = getPatientId();
  const patientScoped = window.location.pathname.startsWith("/patients/");
  const [records, setRecords] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [status, setStatus] = useState("All");
  const [source, setSource] = useState("All");
  const [doctor, setDoctor] = useState("All");
  const [memoryVersion, setMemoryVersion] = useState("All");
  const [hasConflicts, setHasConflicts] = useState(false);
  const [hasStates, setHasStates] = useState(false);
  const [citedOnly, setCitedOnly] = useState(false);
  const [pendingReview, setPendingReview] = useState(false);
  const [selectedEvidence, setSelectedEvidence] = useState(null);
  const [selectedRows, setSelectedRows] = useState([]);
  const [view, setView] = useState("Table");
  const relationships = useMemo(() => buildEvidenceRelationships(records), [records]);
  const categoryOptions = useMemo(() => optionList(records.map((record) => record.category)), [records]);
  const statusOptions = useMemo(() => optionList(records.map((record) => record.evidenceStatus)), [records]);
  const sourceOptions = useMemo(() => optionList(records.map((record) => record.sourceType)), [records]);
  const doctorOptions = useMemo(() => optionList(records.map((record) => record.doctorName).filter(Boolean)), [records]);
  const memoryVersionOptions = useMemo(() => optionList(records.map((record) => record.memoryVersion)), [records]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(searchTerm), 250);
    return () => window.clearTimeout(timer);
  }, [searchTerm]);

  useEffect(() => {
    let mounted = true;
    setIsLoading(true);

    fetchPatientEvidence(patientId)
      .then((items) => {
        if (!mounted) {
          return;
        }

        setRecords(items);
        setLoadError("");
      })
      .catch((error) => {
        if (!mounted) {
          return;
        }

        setLoadError(error.message || "Evidence could not be loaded.");
      })
      .finally(() => {
        if (mounted) {
          setIsLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [patientId]);

  const visibleRecords = useMemo(() => {
    const scoped = patientScoped
      ? records.filter((record) => record.patientId === patientId)
      : records;

    return scoped.filter((record) => {
      const query = debouncedSearch.trim().toLowerCase();
      const searchable = [
        record.id,
        record.summary,
        record.originalText,
        record.patientName,
        record.patientSystemId,
        record.sourceTitle,
        record.category,
        record.sourceType,
        record.doctorName,
      ]
        .join(" ")
        .toLowerCase();

      return (
        (!query || searchable.includes(query)) &&
        (category === "All" || record.category === category) &&
        (status === "All" || record.evidenceStatus === status) &&
        (source === "All" || record.sourceType === source) &&
        (doctor === "All" || record.doctorName === doctor) &&
        (memoryVersion === "All" || String(record.memoryVersion) === memoryVersion) &&
        (!hasConflicts || record.hasConflict) &&
        (!hasStates || record.derivedStateCount > 0) &&
        (!citedOnly || record.citationUsageCount > 0) &&
        (!pendingReview || record.evidenceStatus === "Pending Review")
      );
    });
  }, [
    records,
    patientScoped,
    patientId,
    debouncedSearch,
    category,
    status,
    source,
    doctor,
    memoryVersion,
    hasConflicts,
    hasStates,
    citedOnly,
    pendingReview,
  ]);

  function toggleSelected(id) {
    setSelectedRows((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    );
  }

  function clearFilters() {
    setSearchTerm("");
    setCategory("All");
    setStatus("All");
    setSource("All");
    setDoctor("All");
    setMemoryVersion("All");
    setHasConflicts(false);
    setHasStates(false);
    setCitedOnly(false);
    setPendingReview(false);
  }

  return (
    <PlatformShell sectionLabel="Evidence explorer">
      {patientScoped ? <BackButton label="Back to patient overview" to={`/patients/${patientId}`} /> : null}
      {patientScoped ? <PatientBanner patient={platformPatient} /> : null}

      <div className={patientScoped ? "mt-6" : ""}>
        <PageHero
          eyebrow={patientScoped ? platformPatient.systemPatientId : "Organization evidence"}
          title="Evidence Explorer"
          description="Search, review, and trace clinical evidence across source documents, patient information, computational states, and generated responses."
          actions={
            <>
              <SecondaryButton onClick={() => setView(view === "Table" ? "Relationships" : "Table")}>
                <GitBranch className="h-4 w-4" aria-hidden="true" />
                {view === "Table" ? "Evidence Relationships" : "Evidence Table"}
              </SecondaryButton>
              <SecondaryButton>
                <Download className="h-4 w-4" aria-hidden="true" />
                Export Selected
              </SecondaryButton>
            </>
          }
        />
      </div>

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_170px_170px_190px]">
          <label className="relative block">
            <span className="mb-2 block text-sm font-medium text-slate-700">Search</span>
            <Search className="pointer-events-none absolute left-3 top-[42px] h-4 w-4 text-slate-400" aria-hidden="true" />
            <input
              type="search"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search evidence, patients, documents, and doctors..."
              className={inputClass("pl-9")}
            />
          </label>
          <SelectField label="Category" value={category} onChange={setCategory} options={categoryOptions} />
          <SelectField label="Status" value={status} onChange={setStatus} options={statusOptions} />
          <SelectField label="Source type" value={source} onChange={setSource} options={sourceOptions} />
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-4">
          <SelectField label="Added by doctor" value={doctor} onChange={setDoctor} options={doctorOptions} />
          <SelectField label="Memory version" value={memoryVersion} onChange={setMemoryVersion} options={memoryVersionOptions} />
          <SelectField label="View" value={view} onChange={setView} options={["Table", "Relationships"]} />
        </div>
        <div className="mt-5 flex flex-col gap-3 border-t border-slate-200 pt-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap gap-3">
            <Toggle label="Has conflicts" checked={hasConflicts} onChange={setHasConflicts} />
            <Toggle label="Has derived states" checked={hasStates} onChange={setHasStates} />
            <Toggle label="Cited in answers" checked={citedOnly} onChange={setCitedOnly} />
            <Toggle label="Pending review" checked={pendingReview} onChange={setPendingReview} />
          </div>
          <SecondaryButton onClick={clearFilters}>Clear Filters</SecondaryButton>
        </div>
      </section>

      {loadError ? (
        <div className="mt-6">
          <StatePanel
            title="Evidence request failed"
            text={loadError}
            action={<PrimaryButton onClick={() => window.location.reload()}>Retry</PrimaryButton>}
          />
        </div>
      ) : null}

      {isLoading ? (
        <EvidenceSkeleton />
      ) : null}

      {!isLoading && !loadError && visibleRecords.length === 0 ? (
        <div className="mt-6">
          <EmptyState
            title="No evidence found"
            text={records.length ? "No evidence matches the selected filters." : "Add patient information, upload a document, or approve a chat-derived CSM proposal to create evidence."}
            action={<SecondaryButton onClick={clearFilters}>Clear Filters</SecondaryButton>}
          />
        </div>
      ) : null}

      {!isLoading && !loadError && visibleRecords.length > 0 && view === "Table" ? (
        <section className="mt-6 space-y-4">
          <BulkActions selectedCount={selectedRows.length} />
          <EvidenceTable
            records={visibleRecords}
            selectedRows={selectedRows}
            toggleSelected={toggleSelected}
            setSelectedEvidence={setSelectedEvidence}
          />
        </section>
      ) : null}

      {!isLoading && !loadError && view === "Relationships" ? (
        <RelationshipsView
          records={records}
          relationships={relationships}
          setSelectedEvidence={setSelectedEvidence}
        />
      ) : null}

      {selectedEvidence ? (
        <EvidenceDrawer
          evidence={selectedEvidence}
          onClose={() => setSelectedEvidence(null)}
        />
      ) : null}
    </PlatformShell>
  );
}

function EvidenceTable({ records, selectedRows, toggleSelected, setSelectedEvidence }) {
  return (
    <TableShell
      caption="Evidence records"
      columns={[
        "",
        "Evidence",
        "Patient",
        "Category",
        "Source",
        "Effective Date",
        "Verification",
        "Status",
        "Memory",
        "States",
        "Citations",
        "Actions",
      ]}
    >
      {records.map((record) => (
        <tr key={record.id} className="hover:bg-slate-50">
          <td className="px-5 py-4">
            <input
              type="checkbox"
              checked={selectedRows.includes(record.id)}
              onChange={() => toggleSelected(record.id)}
              className="h-4 w-4 rounded border-slate-300 text-blue-700 focus:ring-blue-200"
              aria-label={`Select ${record.id}`}
            />
          </td>
          <td className="max-w-md px-5 py-4">
            <p className="text-sm font-semibold text-slate-950">{record.summary}</p>
            <p className="mt-1 text-xs text-slate-500">{record.id}</p>
            <p className="mt-1 text-xs text-slate-500">{record.sourceTitle}</p>
          </td>
          <td className="px-5 py-4 text-sm text-slate-600">{record.patientName}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{record.category}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{record.sourceType}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{record.effectiveAt}</td>
          <td className="px-5 py-4"><StatusBadge label={record.verificationStatus} /></td>
          <td className="px-5 py-4"><StatusBadge label={record.evidenceStatus} /></td>
          <td className="px-5 py-4 text-sm text-slate-600">{record.memoryVersion}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{record.derivedStateCount}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{record.citationUsageCount}</td>
          <td className="px-5 py-4">
            <div className="flex flex-wrap gap-2">
              <SecondaryButton onClick={() => setSelectedEvidence(record)}>View</SecondaryButton>
              <SecondaryButton onClick={() => go(`/patients/${record.patientId}/timeline`)}>Timeline</SecondaryButton>
              <SecondaryButton onClick={() => go(`/patients/${record.patientId}/csm`)}>States</SecondaryButton>
            </div>
          </td>
        </tr>
      ))}
    </TableShell>
  );
}

function RelationshipsView({ records, relationships, setSelectedEvidence }) {
  return (
    <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-950">Evidence Relationships</h2>
      <p className="mt-2 text-sm text-slate-600">
        List-based relationship view for traceability without rendering a full graph.
      </p>
      <div className="mt-5 space-y-3">
        {relationships.map((relationship) => (
          <article key={`${relationship.from}-${relationship.relationship}-${relationship.to}`} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <button
                  type="button"
                  onClick={() => setSelectedEvidence(records.find((record) => record.id === relationship.from))}
                  className="font-semibold text-blue-700"
                >
                  {relationship.from}
                </button>
                <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-600">
                  {relationship.relationship}
                </span>
                <span className="font-semibold text-slate-800">{relationship.to}</span>
              </div>
              <p className="text-sm text-slate-600">{relationship.detail}</p>
            </div>
          </article>
        ))}
        {!relationships.length ? (
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-600">
            No state or review relationships exist for the current evidence set.
          </div>
        ) : null}
      </div>
    </section>
  );
}

function BulkActions({ selectedCount }) {
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm font-medium text-slate-700">
        {selectedCount} evidence item{selectedCount === 1 ? "" : "s"} selected
      </p>
      <div className="flex flex-wrap gap-2">
        <SecondaryButton disabled={!selectedCount}>Mark for Review</SecondaryButton>
        <SecondaryButton disabled={!selectedCount}>Export Selected</SecondaryButton>
        <SecondaryButton disabled={!selectedCount}>Add Label</SecondaryButton>
        <SecondaryButton disabled={!selectedCount}>Remove Label</SecondaryButton>
      </div>
    </section>
  );
}

function EvidenceDrawer({ evidence, onClose }) {
  return (
    <Drawer title={evidence.summary} subtitle="Evidence Details" onClose={onClose}>
      <div className="space-y-5">
        <p className="text-sm leading-6 text-slate-700">{evidence.originalText}</p>
        <dl className="grid gap-3 text-sm">
          <InfoRow label="Evidence ID" value={evidence.id} />
          <InfoRow label="Patient" value={evidence.patientName} />
          <InfoRow label="Source" value={`${evidence.sourceType} - ${evidence.sourceTitle}`} />
          <InfoRow label="Effective date" value={evidence.effectiveAt} />
          <InfoRow label="Ingestion date" value={evidence.ingestedAt} />
          <InfoRow label="Memory version" value={evidence.memoryVersion} />
          <InfoRow label="Related evidence" value={evidence.relatedEvidenceCount} />
          <InfoRow label="Derived states" value={evidence.derivedStateCount} />
          <InfoRow label="Answers citing evidence" value={evidence.citationUsageCount} />
        </dl>
        <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <h3 className="text-sm font-semibold text-slate-950">Lineage and usage</h3>
          <div className="mt-3 grid gap-2 text-sm text-slate-600">
            <p>Source lineage: source document to extracted observation to evidence record.</p>
            <p>Processing trace: trace-evidence-{evidence.id}</p>
            <p>Audit history: created, indexed, reviewed, cited.</p>
          </div>
        </section>
        <div className="flex flex-wrap gap-2">
          <SecondaryButton onClick={() => openSource(evidence)}>
            <FileText className="h-4 w-4" aria-hidden="true" />
            Open Source
          </SecondaryButton>
          <SecondaryButton onClick={() => go(`/patients/${evidence.patientId}/timeline`)}>
            <BookOpenText className="h-4 w-4" aria-hidden="true" />
            View Timeline
          </SecondaryButton>
          <SecondaryButton onClick={() => go(`/patients/${evidence.patientId}/csm`)}>
            View Related States
          </SecondaryButton>
        </div>
      </div>
    </Drawer>
  );
}

function openSource(evidence) {
  if (evidence.documentId) {
    go(`/patients/${evidence.patientId}/documents/${evidence.documentId}`);
    return;
  }

  if (evidence.conversationId) {
    go(`/patients/${evidence.patientId}/chat`);
    return;
  }

  go(`/patients/${evidence.patientId}/information`);
}

function optionList(values) {
  return ["All", ...Array.from(new Set(values.filter(Boolean))).sort()];
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 rounded border-slate-300 text-blue-700 focus:ring-blue-200"
      />
      {label}
    </label>
  );
}

function EvidenceSkeleton() {
  return (
    <div className="mt-6 space-y-3">
      {[1, 2, 3].map((item) => (
        <div key={item} className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="h-4 w-40 rounded bg-slate-200" />
          <div className="mt-3 h-5 w-2/3 rounded bg-slate-200" />
          <div className="mt-2 h-4 w-full rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}
