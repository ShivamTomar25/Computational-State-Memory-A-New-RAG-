import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  BookOpenText,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Database,
  FileText,
  FlaskConical,
  HeartPulse,
  History,
  LogOut,
  Pill,
  Plus,
  RefreshCcw,
  Search,
  ShieldCheck,
  Stethoscope,
  UserRound,
  X,
} from "lucide-react";
import {
  fetchPatientTimeline,
  getCachedPatientTimelineEvents,
  timelineCategories,
  timelineEvidenceStatuses,
  timelinePatient,
  timelineSourceTypes,
} from "./patientTimelineService";

const navigationItems = [
  "Overview",
  "Chat",
  "Documents",
  "Timeline",
  "Patient Information",
  "Compare",
];

const statusStyles = {
  Active: "border-green-200 bg-green-50 text-green-700",
  Superseded: "border-slate-200 bg-slate-50 text-slate-600",
  Retracted: "border-red-200 bg-red-50 text-red-700",
  Contested: "border-amber-200 bg-amber-50 text-amber-700",
  "Pending Review": "border-blue-200 bg-blue-50 text-blue-700",
  "Confirmed by Doctor": "border-green-200 bg-green-50 text-green-700",
  "Imported from Record": "border-slate-200 bg-slate-50 text-slate-600",
  "System Event": "border-blue-200 bg-blue-50 text-blue-700",
  "Conversation History": "border-slate-200 bg-slate-50 text-slate-600",
};

export function PatientTimelinePage() {
  const patientId = getPatientId();
  const [events, setEvents] = useState(() => getCachedPatientTimelineEvents(patientId));
  const [isLoading, setIsLoading] = useState(true);
  const [demoState, setDemoState] = useState("ready");
  const [searchTerm, setSearchTerm] = useState("");
  const [dateRange, setDateRange] = useState("All Time");
  const [customFrom, setCustomFrom] = useState("");
  const [customTo, setCustomTo] = useState("");
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [selectedStatuses, setSelectedStatuses] = useState([]);
  const [selectedSources, setSelectedSources] = useState([]);
  const [sortMode, setSortMode] = useState("Newest Effective Date");
  const [showSystemActivity, setShowSystemActivity] = useState(false);
  const [density, setDensity] = useState("Comfortable");
  const [expandedEventId, setExpandedEventId] = useState(null);
  const [selectedEvidence, setSelectedEvidence] = useState(null);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    fetchPatientTimeline(patientId)
      .then((items) => {
        if (!isMounted) {
          return;
        }

        setEvents(items);
        setDemoState("ready");
      })
      .catch(() => {
        if (!isMounted) {
          return;
        }

        setEvents([]);
        setDemoState("error");
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [patientId]);

  const activeEvents = demoState === "empty" ? [] : events;
  const filteredEvents = useMemo(
    () =>
      filterTimelineEvents(activeEvents, {
        searchTerm,
        dateRange,
        customFrom,
        customTo,
        selectedCategories,
        selectedStatuses,
        selectedSources,
        sortMode,
        showSystemActivity,
      }),
    [
      activeEvents,
      searchTerm,
      dateRange,
      customFrom,
      customTo,
      selectedCategories,
      selectedStatuses,
      selectedSources,
      sortMode,
      showSystemActivity,
    ],
  );
  const groupedEvents = useMemo(() => groupEventsByDate(filteredEvents), [filteredEvents]);
  const filtersActive =
    searchTerm ||
    dateRange !== "All Time" ||
    selectedCategories.length ||
    selectedStatuses.length ||
    selectedSources.length ||
    showSystemActivity;

  function clearFilters() {
    setSearchTerm("");
    setDateRange("All Time");
    setCustomFrom("");
    setCustomTo("");
    setSelectedCategories([]);
    setSelectedStatuses([]);
    setSelectedSources([]);
    setSortMode("Newest Effective Date");
    setShowSystemActivity(false);
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <WorkspaceHeader patientId={patientId} sectionLabel="Patient timeline" />

      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
        <BackAndBreadcrumb patientId={patientId} current="Timeline" />
        <PatientContext />
        <WorkspaceNavigation activeItem="Timeline" patientId={patientId} />

        <section className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-slate-950">
                Patient Timeline
              </h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                Review the chronological clinical history, evidence updates,
                and memory changes for this patient.
              </p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => window.location.assign(`/patients/${patientId}/documents`)}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
              >
                <FileText className="h-4 w-4" aria-hidden="true" />
                Upload Document
              </button>
              <button
                type="button"
                onClick={() => window.location.assign(`/patients/${patientId}/information`)}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200"
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
                Add Information
              </button>
            </div>
          </div>
        </section>

        <TimelineToolbar
          searchTerm={searchTerm}
          setSearchTerm={setSearchTerm}
          dateRange={dateRange}
          setDateRange={setDateRange}
          customFrom={customFrom}
          setCustomFrom={setCustomFrom}
          customTo={customTo}
          setCustomTo={setCustomTo}
          selectedCategories={selectedCategories}
          setSelectedCategories={setSelectedCategories}
          selectedStatuses={selectedStatuses}
          setSelectedStatuses={setSelectedStatuses}
          selectedSources={selectedSources}
          setSelectedSources={setSelectedSources}
          sortMode={sortMode}
          setSortMode={setSortMode}
          showSystemActivity={showSystemActivity}
          setShowSystemActivity={setShowSystemActivity}
          density={density}
          setDensity={setDensity}
          demoState={demoState}
          setDemoState={setDemoState}
          onClear={clearFilters}
        />

        <section className="mt-6" aria-live="polite">
          {isLoading || demoState === "loading" ? <TimelineSkeleton /> : null}
          {!isLoading && demoState === "error" ? (
            <StateCard
              icon={<AlertCircle className="h-5 w-5" aria-hidden="true" />}
              title="Timeline could not be loaded"
              text="The timeline request failed. Retry after checking the patient workspace session."
              actionLabel="Retry"
              onAction={() => setDemoState("ready")}
            />
          ) : null}
          {!isLoading && demoState === "permission" ? (
            <StateCard
              icon={<ShieldCheck className="h-5 w-5" aria-hidden="true" />}
              title="Permission denied"
              text="This doctor account is not authorized to view timeline events for this patient."
              actionLabel="Back to patients"
              onAction={() => window.location.assign("/patients")}
            />
          ) : null}
          {!isLoading && demoState === "ready" && groupedEvents.length === 0 ? (
            <EmptyTimeline filtersActive={Boolean(filtersActive)} onClear={clearFilters} patientId={patientId} />
          ) : null}
          {!isLoading && demoState === "empty" ? (
            <EmptyTimeline filtersActive={false} onClear={clearFilters} patientId={patientId} />
          ) : null}
          {!isLoading && demoState === "ready" && groupedEvents.length > 0 ? (
            <div className="space-y-8">
              {groupedEvents.map((group) => (
                <TimelineDateGroup
                  key={group.dateLabel}
                  group={group}
                  density={density}
                  expandedEventId={expandedEventId}
                  setExpandedEventId={setExpandedEventId}
                  setSelectedEvidence={setSelectedEvidence}
                  patientId={patientId}
                />
              ))}
            </div>
          ) : null}
        </section>
      </main>

      {selectedEvidence ? (
        <EvidenceDrawer
          evidence={selectedEvidence}
          onClose={() => setSelectedEvidence(null)}
        />
      ) : null}
    </div>
  );
}

function TimelineToolbar({
  searchTerm,
  setSearchTerm,
  dateRange,
  setDateRange,
  customFrom,
  setCustomFrom,
  customTo,
  setCustomTo,
  selectedCategories,
  setSelectedCategories,
  selectedStatuses,
  setSelectedStatuses,
  selectedSources,
  setSelectedSources,
  sortMode,
  setSortMode,
  showSystemActivity,
  setShowSystemActivity,
  density,
  setDensity,
  demoState,
  setDemoState,
  onClear,
}) {
  return (
    <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px_210px_190px]">
        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">
            Search
          </span>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" aria-hidden="true" />
            <input
              type="search"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search timeline events..."
              className={inputClass("pl-9")}
            />
          </div>
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">
            Date range
          </span>
          <select
            value={dateRange}
            onChange={(event) => setDateRange(event.target.value)}
            className={inputClass()}
          >
            {["All Time", "Last 7 Days", "Last 30 Days", "Last 90 Days", "Custom Range"].map((option) => (
              <option key={option}>{option}</option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">
            Sort
          </span>
          <select
            value={sortMode}
            onChange={(event) => setSortMode(event.target.value)}
            className={inputClass()}
          >
            {["Newest Effective Date", "Oldest Effective Date", "Recently Added"].map((option) => (
              <option key={option}>{option}</option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-2 block text-sm font-medium text-slate-700">
            Demo state
          </span>
          <select
            value={demoState}
            onChange={(event) => setDemoState(event.target.value)}
            className={inputClass()}
          >
            <option value="ready">Ready</option>
            <option value="loading">Loading</option>
            <option value="empty">Empty</option>
            <option value="error">Failed request</option>
            <option value="permission">Permission denied</option>
          </select>
        </label>
      </div>

      {dateRange === "Custom Range" ? (
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:max-w-xl">
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-700">
              From
            </span>
            <input
              type="date"
              value={customFrom}
              onChange={(event) => setCustomFrom(event.target.value)}
              className={inputClass()}
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-700">
              To
            </span>
            <input
              type="date"
              value={customTo}
              onChange={(event) => setCustomTo(event.target.value)}
              className={inputClass()}
            />
          </label>
        </div>
      ) : null}

      <div className="mt-5 grid gap-4 lg:grid-cols-3">
        <CheckboxGroup
          title="Event types"
          options={timelineCategories}
          values={selectedCategories}
          onChange={setSelectedCategories}
        />
        <CheckboxGroup
          title="Evidence status"
          options={timelineEvidenceStatuses}
          values={selectedStatuses}
          onChange={setSelectedStatuses}
        />
        <CheckboxGroup
          title="Source"
          options={timelineSourceTypes}
          values={selectedSources}
          onChange={setSelectedSources}
        />
      </div>

      <div className="mt-5 flex flex-col gap-3 border-t border-slate-200 pt-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-3">
          <label className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={showSystemActivity}
              onChange={(event) => setShowSystemActivity(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-blue-700 focus:ring-blue-200"
            />
            Show system activity
          </label>
          <div className="inline-flex rounded-lg border border-slate-300 bg-white p-1">
            {["Comfortable", "Compact"].map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setDensity(option)}
                className={`h-8 rounded-md px-3 text-sm font-medium ${
                  density === option
                    ? "bg-blue-700 text-white"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        <button
          type="button"
          onClick={onClear}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
        >
          <RefreshCcw className="h-4 w-4" aria-hidden="true" />
          Clear Filters
        </button>
      </div>
    </section>
  );
}

function CheckboxGroup({ title, options, values, onChange }) {
  function toggle(option) {
    onChange(
      values.includes(option)
        ? values.filter((value) => value !== option)
        : [...values, option],
    );
  }

  return (
    <fieldset className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <legend className="px-1 text-sm font-semibold text-slate-950">
        {title}
      </legend>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {options.map((option) => (
          <label key={option} className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={values.includes(option)}
              onChange={() => toggle(option)}
              className="h-4 w-4 rounded border-slate-300 text-blue-700 focus:ring-blue-200"
            />
            <span>{option}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function TimelineDateGroup({
  group,
  density,
  expandedEventId,
  setExpandedEventId,
  setSelectedEvidence,
  patientId,
}) {
  return (
    <section>
      <div className="mb-4 flex items-center gap-3">
        <CalendarDays className="h-5 w-5 text-blue-700" aria-hidden="true" />
        <h2 className="text-base font-semibold text-slate-950">
          {group.dateLabel}
        </h2>
      </div>
      <div className="relative space-y-4 border-l border-slate-200 pl-5">
        {group.events.map((event) => (
          <TimelineEventCard
            key={event.id}
            event={event}
            density={density}
            expanded={expandedEventId === event.id}
            onToggle={() =>
              setExpandedEventId(expandedEventId === event.id ? null : event.id)
            }
            onEvidence={() => setSelectedEvidence(buildEvidenceFromEvent(event))}
            patientId={patientId}
          />
        ))}
      </div>
    </section>
  );
}

function TimelineEventCard({ event, density, expanded, onToggle, onEvidence, patientId }) {
  const isCompact = density === "Compact";

  return (
    <article className={`${event.isSystemActivity ? "bg-slate-50" : "bg-white"} rounded-xl border border-slate-200 p-5 shadow-sm`}>
      <div className="absolute -left-[10px] mt-1 flex h-5 w-5 items-center justify-center rounded-full border border-blue-200 bg-white text-blue-700">
        <span className="h-2 w-2 rounded-full bg-blue-700" />
      </div>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
              {eventIcon(event.category)}
            </div>
            <span className="text-xs font-semibold uppercase text-slate-500">
              {event.category}
            </span>
            <StatusBadge label={event.evidenceStatus} />
            <StatusBadge label={event.verificationStatus} />
          </div>
          <h3 className="mt-3 text-base font-semibold text-slate-950">
            {event.title}
          </h3>
          <p className={`${isCompact ? "mt-1" : "mt-2"} text-sm leading-6 text-slate-600`}>
            {event.summary}
          </p>
          <div className={`${isCompact ? "mt-3" : "mt-4"} grid gap-2 text-sm text-slate-600 sm:grid-cols-2`}>
            <p>Effective: {formatEffective(event.effectiveAt)}</p>
            <p>Added: {formatDateTime(event.ingestedAt)}</p>
            <p>Source: {event.sourceType}</p>
            <p>Memory version: {event.patientMemoryVersion}</p>
            <p>Added by: {event.addedBy?.name || "Not recorded"}</p>
            <p>Source title: {event.sourceTitle}</p>
          </div>
        </div>

        <button
          type="button"
          onClick={onToggle}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
          aria-expanded={expanded}
        >
          {expanded ? "Hide Details" : "View Details"}
          <ChevronDown className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>

      {event.supersedesEventId ? (
        <RelationshipBanner text={`Supersedes entry from ${event.supersedesEventId}`} />
      ) : null}
      {event.supersededByEventId ? (
        <RelationshipBanner text={`Superseded by ${event.supersededByEventId}`} />
      ) : null}

      {expanded ? (
        <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <h4 className="text-sm font-semibold text-slate-950">
            Original text
          </h4>
          <p className="mt-2 text-sm leading-6 text-slate-700">
            {event.originalText}
          </p>
          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <InfoRow label="Evidence lineage" value={event.relatedEvidenceIds.join(", ") || "No linked evidence"} />
            <InfoRow label="State updates" value={event.causedStateIds?.join(", ") || "None"} />
            <InfoRow label="Processing status" value={event.processingStatus || "Ready"} />
            <InfoRow label="Source reference" value={event.sourceId || "Not recorded"} />
          </dl>
          <div className="mt-4 flex flex-wrap gap-2">
            <SmallAction label="View Evidence" icon={<ClipboardList className="h-4 w-4" aria-hidden="true" />} onClick={onEvidence} />
            {event.sourceId?.startsWith("doc-") ? (
              <SmallAction
                label="Open Original Document"
                icon={<FileText className="h-4 w-4" aria-hidden="true" />}
                onClick={() => window.location.assign(`/patients/${patientId}/documents/${event.sourceId}`)}
              />
            ) : null}
            <SmallAction label="View Related Events" icon={<History className="h-4 w-4" aria-hidden="true" />} />
            <SmallAction label="View State Changes" icon={<Database className="h-4 w-4" aria-hidden="true" />} onClick={() => window.location.assign(`/patients/${patientId}/csm`)} />
            {event.evidenceStatus !== "Retracted" ? (
              <SmallAction label="Add Correction" icon={<Plus className="h-4 w-4" aria-hidden="true" />} />
            ) : null}
          </div>
        </div>
      ) : null}
    </article>
  );
}

function EmptyTimeline({ filtersActive, onClear, patientId }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white px-6 py-12 text-center">
      <History className="mx-auto h-10 w-10 text-slate-400" aria-hidden="true" />
      <h2 className="mt-4 text-lg font-semibold text-slate-950">
        No timeline events found
      </h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">
        {filtersActive
          ? "No events match the selected filters."
          : "Upload a document or add patient information to begin building this patient's timeline."}
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <SmallAction
          label="Upload Document"
          icon={<FileText className="h-4 w-4" aria-hidden="true" />}
          onClick={() => window.location.assign(`/patients/${patientId}/documents`)}
        />
        <SmallAction
          label="Add Patient Information"
          icon={<BookOpenText className="h-4 w-4" aria-hidden="true" />}
          onClick={() => window.location.assign(`/patients/${patientId}/information`)}
        />
        {filtersActive ? (
          <SmallAction
            label="Clear Filters"
            icon={<RefreshCcw className="h-4 w-4" aria-hidden="true" />}
            onClick={onClear}
          />
        ) : null}
      </div>
    </section>
  );
}

function StateCard({ icon, title, text, actionLabel, onAction }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <div className="flex gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-red-50 text-red-700">
          {icon}
        </div>
        <div>
          <h2 className="text-base font-semibold text-slate-950">{title}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">{text}</p>
          <button
            type="button"
            onClick={onAction}
            className="mt-4 inline-flex h-10 items-center justify-center rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200"
          >
            {actionLabel}
          </button>
        </div>
      </div>
    </section>
  );
}

function TimelineSkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((item) => (
        <div key={item} className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="h-4 w-32 rounded bg-slate-200" />
          <div className="mt-4 h-5 w-2/3 rounded bg-slate-200" />
          <div className="mt-3 h-4 w-full rounded bg-slate-100" />
          <div className="mt-2 h-4 w-4/5 rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}

function EvidenceDrawer({ evidence, onClose }) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-950/30" role="dialog" aria-modal="true">
      <div className="ml-auto flex h-full w-full max-w-xl flex-col bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">
              Evidence Details
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-950">
              {evidence.title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 focus:outline-none focus:ring-4 focus:ring-blue-100"
            aria-label="Close evidence details"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <div className="flex-1 space-y-5 overflow-y-auto p-5">
          <StatusBadge label={evidence.status} />
          <p className="text-sm leading-6 text-slate-700">{evidence.excerpt}</p>
          <dl className="grid gap-3 text-sm">
            <InfoRow label="Source" value={evidence.source} />
            <InfoRow label="Effective date" value={evidence.effective} />
            <InfoRow label="Verification" value={evidence.verification} />
            <InfoRow label="Patient memory version" value={evidence.memoryVersion} />
          </dl>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="text-sm font-semibold text-slate-950">
              Evidence lineage
            </p>
            <div className="mt-3 space-y-2 text-sm text-slate-600">
              {["Original Source", "Extracted Observation", "Timeline Event", "Patient Memory"].map((step) => (
                <div key={step} className="flex items-center gap-2">
                  <ChevronRight className="h-4 w-4 text-blue-700" aria-hidden="true" />
                  {step}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PatientContext() {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">
            Patient: {timelinePatient.displayName} - {timelinePatient.systemPatientId}
          </p>
          <h1 className="mt-2 text-2xl font-semibold text-slate-950">
            {timelinePatient.displayName}
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {timelinePatient.age} years, {timelinePatient.sex}. Primary
            condition: {timelinePatient.primaryCondition}
          </p>
        </div>
        <div className="grid gap-2 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 sm:grid-cols-2">
          <p>Patient memory version: {timelinePatient.memoryVersion}</p>
          <p>Last updated: {timelinePatient.lastUpdated}</p>
        </div>
      </div>
    </section>
  );
}

function WorkspaceHeader({ patientId, sectionLabel }) {
  return (
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
            <p className="text-xs text-slate-500">{sectionLabel}</p>
          </div>
        </button>
        <div className="flex items-center gap-2 sm:gap-4">
          <button
            type="button"
            className="hidden h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100 sm:flex"
          >
            <UserRound className="h-4 w-4" aria-hidden="true" />
            Doctor
          </button>
          <button
            type="button"
            onClick={() => window.location.assign("/")}
            className="flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            <span className="hidden sm:inline">Logout</span>
          </button>
        </div>
      </div>
    </header>
  );
}

function BackAndBreadcrumb({ patientId, current }) {
  return (
    <>
      <button
        type="button"
        onClick={() => window.location.assign(`/patients/${patientId}`)}
        className="mb-5 inline-flex items-center gap-2 rounded text-sm font-medium text-slate-600 transition hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-blue-100"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to patient overview
      </button>
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
          {timelinePatient.displayName}
        </button>
        <span aria-hidden="true">/</span>
        <span className="font-medium text-slate-700">{current}</span>
      </nav>
    </>
  );
}

function WorkspaceNavigation({ activeItem, patientId }) {
  const routes = {
    Overview: `/patients/${patientId}`,
    Chat: `/patients/${patientId}/chat`,
    Documents: `/patients/${patientId}/documents`,
    Timeline: `/patients/${patientId}/timeline`,
    "Patient Information": `/patients/${patientId}/information`,
    Compare: `/patients/${patientId}/compare`,
  };

  return (
    <nav className="mt-6 overflow-x-auto border-b border-slate-200">
      <div className="flex min-w-max gap-1">
        {navigationItems.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => window.location.assign(routes[item])}
            className={`h-11 whitespace-nowrap border-b-2 px-4 text-sm font-medium ${
              item === activeItem
                ? "border-blue-700 text-blue-700"
                : "border-transparent text-slate-600 hover:text-slate-950"
            }`}
          >
            {item}
          </button>
        ))}
      </div>
    </nav>
  );
}

function RelationshipBanner({ text }) {
  return (
    <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-800">
      {text}
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value}</dd>
    </div>
  );
}

function SmallAction({ icon, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
    >
      {icon}
      {label}
    </button>
  );
}

function StatusBadge({ label }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${statusStyles[label] || "border-slate-200 bg-slate-50 text-slate-600"}`}>
      {label}
    </span>
  );
}

function eventIcon(category) {
  if (category === "Medication") {
    return <Pill className="h-4 w-4" aria-hidden="true" />;
  }

  if (category === "Laboratory Result") {
    return <FlaskConical className="h-4 w-4" aria-hidden="true" />;
  }

  if (category === "Vital Sign") {
    return <HeartPulse className="h-4 w-4" aria-hidden="true" />;
  }

  if (category === "Memory Updates") {
    return <Database className="h-4 w-4" aria-hidden="true" />;
  }

  if (category === "Symptom" || category === "Diagnosis") {
    return <Stethoscope className="h-4 w-4" aria-hidden="true" />;
  }

  if (category === "Documents") {
    return <FileText className="h-4 w-4" aria-hidden="true" />;
  }

  return <ClipboardList className="h-4 w-4" aria-hidden="true" />;
}

function filterTimelineEvents(events, filters) {
  const query = filters.searchTerm.trim().toLowerCase();
  const minDate = getRangeStart(filters.dateRange, filters.customFrom);
  const maxDate = filters.dateRange === "Custom Range" && filters.customTo
    ? new Date(`${filters.customTo}T23:59:59`)
    : null;

  return [...events]
    .filter((event) => filters.showSystemActivity || !event.isSystemActivity)
    .filter((event) => {
      if (!query) {
        return true;
      }

      return [
        event.title,
        event.summary,
        event.sourceTitle,
        event.sourceType,
        event.addedBy?.name,
        event.originalText,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(query);
    })
    .filter((event) => !filters.selectedCategories.length || filters.selectedCategories.includes(event.category))
    .filter((event) => !filters.selectedStatuses.length || filters.selectedStatuses.includes(event.evidenceStatus))
    .filter((event) => !filters.selectedSources.length || filters.selectedSources.includes(event.sourceType))
    .filter((event) => {
      if (!minDate && !maxDate) {
        return true;
      }

      const effective = event.effectiveAt ? new Date(event.effectiveAt) : null;

      if (!effective) {
        return false;
      }

      if (minDate && effective < minDate) {
        return false;
      }

      if (maxDate && effective > maxDate) {
        return false;
      }

      return true;
    })
    .sort((first, second) => sortEvents(first, second, filters.sortMode));
}

function sortEvents(first, second, sortMode) {
  const firstDate = new Date(first.effectiveAt || "1900-01-01").getTime();
  const secondDate = new Date(second.effectiveAt || "1900-01-01").getTime();
  const firstIngested = new Date(first.ingestedAt).getTime();
  const secondIngested = new Date(second.ingestedAt).getTime();

  if (sortMode === "Oldest Effective Date") {
    return firstDate - secondDate;
  }

  if (sortMode === "Recently Added") {
    return secondIngested - firstIngested;
  }

  return secondDate - firstDate;
}

function groupEventsByDate(events) {
  return events.reduce((groups, event) => {
    const dateLabel = event.effectiveAt
      ? formatDateOnly(event.effectiveAt)
      : "Date not recorded";
    const existing = groups.find((group) => group.dateLabel === dateLabel);

    if (existing) {
      existing.events.push(event);
    } else {
      groups.push({ dateLabel, events: [event] });
    }

    return groups;
  }, []);
}

function getRangeStart(dateRange, customFrom) {
  if (dateRange === "All Time") {
    return null;
  }

  if (dateRange === "Custom Range") {
    return customFrom ? new Date(`${customFrom}T00:00:00`) : null;
  }

  const days = {
    "Last 7 Days": 7,
    "Last 30 Days": 30,
    "Last 90 Days": 90,
  }[dateRange];
  const start = new Date("2026-07-17T23:59:59");
  start.setDate(start.getDate() - days);
  return start;
}

function buildEvidenceFromEvent(event) {
  return {
    title: event.sourceTitle || event.title,
    status: event.evidenceStatus,
    excerpt: event.originalText,
    source: event.sourceType,
    effective: formatEffective(event.effectiveAt),
    verification: event.verificationStatus,
    memoryVersion: event.patientMemoryVersion,
  };
}

function formatEffective(value) {
  return value ? formatDateTime(value) : "Time not recorded";
}

function formatDateTime(value) {
  if (!value) {
    return "Not recorded";
  }

  return new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatDateOnly(value) {
  return new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(new Date(value));
}

function inputClass(extra = "") {
  return `h-11 w-full rounded-lg border border-slate-300 bg-white px-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-700 focus:ring-4 focus:ring-blue-100 ${extra}`;
}

function getPatientId() {
  return window.location.pathname.split("/")[2] || timelinePatient.id;
}
