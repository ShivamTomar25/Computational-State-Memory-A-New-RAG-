import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  GitBranch,
  History,
  LogOut,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  UserRound,
  X,
} from "lucide-react";
import {
  csmActivation,
  csmEvidence,
  csmHistory,
  csmLineage,
  csmPatient,
  csmSummary,
  approveCsmReview,
  fetchCsmStates,
  getCachedCsmState,
  rejectCsmReview,
  syncCsm,
} from "./csmService";

const statusStyles = {
  "CSM Ready": "border-green-200 bg-green-50 text-green-700",
  "CSM Processing": "border-amber-200 bg-amber-50 text-amber-700",
  "CSM Out of Sync": "border-amber-200 bg-amber-50 text-amber-700",
  "CSM Failed": "border-red-200 bg-red-50 text-red-700",
  "CSM Not Enabled": "border-slate-200 bg-slate-50 text-slate-600",
  "CSM Not Initialized": "border-slate-200 bg-slate-50 text-slate-600",
  Active: "border-green-200 bg-green-50 text-green-700",
  Candidate: "border-blue-200 bg-blue-50 text-blue-700",
  Contested: "border-red-200 bg-red-50 text-red-700",
  Resolved: "border-green-200 bg-green-50 text-green-700",
  Superseded: "border-slate-200 bg-slate-50 text-slate-600",
  "Pending Review": "border-blue-200 bg-blue-50 text-blue-700",
  "Strongly Supported": "border-green-200 bg-green-50 text-green-700",
  Supported: "border-green-200 bg-green-50 text-green-700",
  "Partially Supported": "border-blue-200 bg-blue-50 text-blue-700",
  "Conflicting Evidence": "border-red-200 bg-red-50 text-red-700",
  "Insufficient Evidence": "border-amber-200 bg-amber-50 text-amber-700",
  Stale: "border-amber-200 bg-amber-50 text-amber-700",
  Unknown: "border-slate-200 bg-slate-50 text-slate-600",
  ActiveEvidence: "border-green-200 bg-green-50 text-green-700",
  Retracted: "border-red-200 bg-red-50 text-red-700",
};

export function ComputationalStateMemoryPage() {
  const patientId = getPatientId();
  const hasActivation = Boolean(new URLSearchParams(window.location.search).get("activationId"));
  const [states, setStates] = useState(() => getCachedCsmState(patientId).states);
  const [isLoading, setIsLoading] = useState(() => getCachedCsmState(patientId).states.length === 0);
  const [availability, setAvailability] = useState("CSM Not Initialized");
  const [searchTerm, setSearchTerm] = useState("");
  const [category, setCategory] = useState("All");
  const [stateStatus, setStateStatus] = useState("All");
  const [supportStatus, setSupportStatus] = useState("All");
  const [updatedFilter, setUpdatedFilter] = useState("All");
  const [evidenceFilter, setEvidenceFilter] = useState("All");
  const [onlyActivated, setOnlyActivated] = useState(hasActivation);
  const [onlyConflicts, setOnlyConflicts] = useState(false);
  const [onlyStale, setOnlyStale] = useState(false);
  const [selectedStateId, setSelectedStateId] = useState("");
  const [selectedEvidence, setSelectedEvidence] = useState(null);
  const [showTechnical, setShowTechnical] = useState(false);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    fetchCsmStates(patientId)
      .then((items) => {
        if (!isMounted) {
          return;
        }

        setStates(items);
        setAvailability(csmSummary.availability || (items.length ? "CSM Ready" : "CSM Not Initialized"));
      })
      .catch(() => {
        if (!isMounted) {
          return;
        }

        setAvailability("CSM Failed");
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

  async function runSync() {
    setAvailability("CSM Processing");

    try {
      await syncCsm(patientId);
      const items = await fetchCsmStates(patientId);
      setStates(items);
      setAvailability(csmSummary.availability || (items.length ? "CSM Ready" : "CSM Not Initialized"));
    } catch {
      setAvailability("CSM Failed");
    }
  }

  async function decideReview(reviewId, decision) {
    if (!reviewId) {
      return;
    }

    setAvailability("CSM Processing");

    try {
      if (decision === "approve") {
        await approveCsmReview(patientId, reviewId);
      } else {
        await rejectCsmReview(patientId, reviewId);
      }

      const items = await fetchCsmStates(patientId);
      setStates(items);
      setSelectedStateId("");
      setAvailability(csmSummary.availability || (items.length ? "CSM Ready" : "CSM Not Initialized"));
    } catch {
      setAvailability("CSM Failed");
    }
  }

  const filteredStates = useMemo(
    () =>
      filterStates(states, {
        searchTerm,
        category,
        stateStatus,
        supportStatus,
        updatedFilter,
        evidenceFilter,
        onlyActivated,
        onlyConflicts,
        onlyStale,
      }),
    [
      states,
      searchTerm,
      category,
      stateStatus,
      supportStatus,
      updatedFilter,
      evidenceFilter,
      onlyActivated,
      onlyConflicts,
      onlyStale,
    ],
  );
  const selectedState =
    states.find((state) => state.id === selectedStateId) || filteredStates[0] || states[0];
  const selectedEvidenceItems = csmEvidence.filter(
    (evidence) => evidence.stateId === selectedState?.id,
  );

  return (
    <div className="min-h-screen bg-slate-50">
      <WorkspaceHeader patientId={patientId} />
      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
        <button
          type="button"
          onClick={() => window.location.assign(`/patients/${patientId}`)}
          className="mb-5 inline-flex items-center gap-2 rounded text-sm font-medium text-slate-600 transition hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-blue-100"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to patient overview
        </button>

        <PatientContext />

        <section className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-2xl font-semibold text-slate-950">
                  Computational State Memory
                </h1>
                <StatusBadge label={availability} />
              </div>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                Inspect the evolving patient state, supporting evidence,
                uncertainty, dependencies, and update history.
              </p>
              <p className="mt-3 text-sm font-medium text-slate-600">
                Computational states are derived objects and do not replace
                original patient evidence.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-[minmax(0,220px)_auto] sm:items-end">
            <label className="block min-w-[220px]">
              <span className="mb-2 block text-sm font-medium text-slate-700">
                Availability state
              </span>
              <select
                value={availability}
                onChange={(event) => setAvailability(event.target.value)}
                className={inputClass()}
              >
                <option>CSM Ready</option>
                <option>CSM Processing</option>
                <option>CSM Out of Sync</option>
                <option>CSM Failed</option>
                <option>CSM Not Enabled</option>
                <option>CSM Not Initialized</option>
              </select>
            </label>
            <button
              type="button"
              onClick={runSync}
              disabled={availability === "CSM Processing"}
              className="inline-flex h-11 items-center justify-center rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Sync CSM
            </button>
            </div>
          </div>
        </section>

        {availability !== "CSM Ready" ? (
          <AvailabilityState availability={availability} patientId={patientId} />
        ) : null}

        {availability === "CSM Ready" ? (
          <>
            <SummaryCards />
            {hasActivation || onlyActivated ? <ActivatedStatesPanel /> : null}
            <StateFilters
              searchTerm={searchTerm}
              setSearchTerm={setSearchTerm}
              category={category}
              setCategory={setCategory}
              stateStatus={stateStatus}
              setStateStatus={setStateStatus}
              supportStatus={supportStatus}
              setSupportStatus={setSupportStatus}
              updatedFilter={updatedFilter}
              setUpdatedFilter={setUpdatedFilter}
              evidenceFilter={evidenceFilter}
              setEvidenceFilter={setEvidenceFilter}
              onlyActivated={onlyActivated}
              setOnlyActivated={setOnlyActivated}
              onlyConflicts={onlyConflicts}
              setOnlyConflicts={setOnlyConflicts}
              onlyStale={onlyStale}
              setOnlyStale={setOnlyStale}
            />

            {isLoading ? (
              <CsmSkeleton />
            ) : (
              <section className="mt-6 grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
                <StateList
                  states={filteredStates}
                  selectedStateId={selectedState?.id}
                  setSelectedStateId={setSelectedStateId}
                />
                <StateDetails
                  state={selectedState}
                  showTechnical={showTechnical}
                  setShowTechnical={setShowTechnical}
                  patientId={patientId}
                  onApproveReview={(reviewId) => decideReview(reviewId, "approve")}
                  onRejectReview={(reviewId) => decideReview(reviewId, "reject")}
                />
                <EvidenceAndLineagePanel
                  evidenceItems={selectedEvidenceItems}
                  setSelectedEvidence={setSelectedEvidence}
                  patientId={patientId}
                />
              </section>
            )}
          </>
        ) : null}
      </main>

      {selectedEvidence ? (
        <EvidenceDrawer
          evidence={selectedEvidence}
          onClose={() => setSelectedEvidence(null)}
          patientId={patientId}
        />
      ) : null}
    </div>
  );
}

function SummaryCards() {
  const rows = [
    ["Patient memory version", csmPatient.memoryVersion],
    ["CSM state version", csmSummary.stateVersion],
    ["Synchronization", csmSummary.syncStatus],
    ["Last state update", csmSummary.lastStateUpdate],
    ["Active states", csmSummary.totalActiveStates],
    ["Contested states", csmSummary.contestedStates],
    ["Pending review", csmSummary.pendingReviewStates],
  ];

  return (
    <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {rows.map(([label, value]) => (
        <article key={label} className="rounded-xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-500">{label}</p>
          <p className="mt-2 text-xl font-semibold text-slate-950">{value}</p>
        </article>
      ))}
    </section>
  );
}

function StateFilters({
  searchTerm,
  setSearchTerm,
  category,
  setCategory,
  stateStatus,
  setStateStatus,
  supportStatus,
  setSupportStatus,
  updatedFilter,
  setUpdatedFilter,
  evidenceFilter,
  setEvidenceFilter,
  onlyActivated,
  setOnlyActivated,
  onlyConflicts,
  setOnlyConflicts,
  onlyStale,
  setOnlyStale,
}) {
  return (
    <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_170px_170px_200px]">
        <label className="relative block">
          <span className="mb-2 block text-sm font-medium text-slate-700">
            Search states
          </span>
          <Search className="pointer-events-none absolute left-3 top-[42px] h-4 w-4 text-slate-400" aria-hidden="true" />
          <input
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search by state name or value"
            className={inputClass("pl-9")}
          />
        </label>
        <FilterSelect label="Category" value={category} onChange={setCategory} options={["All", "Medication", "Diagnosis", "Symptom", "Allergy", "Laboratory", "Vital Sign", "Treatment"]} />
        <FilterSelect label="Status" value={stateStatus} onChange={setStateStatus} options={["All", "Candidate", "Active", "Contested", "Resolved", "Superseded", "Pending Review"]} />
        <FilterSelect label="Support" value={supportStatus} onChange={setSupportStatus} options={["All", "Strongly Supported", "Supported", "Partially Supported", "Conflicting Evidence", "Insufficient Evidence", "Stale", "Unknown"]} />
      </div>
      <div className="mt-4 grid gap-4 lg:grid-cols-[190px_190px_minmax(0,1fr)]">
        <FilterSelect label="Updated date" value={updatedFilter} onChange={setUpdatedFilter} options={["All", "Last 7 Days", "Last 30 Days"]} />
        <FilterSelect label="Evidence count" value={evidenceFilter} onChange={setEvidenceFilter} options={["All", "Has evidence", "Has no evidence"]} />
        <div className="flex flex-wrap items-end gap-3">
          <Toggle label="Show only activated states" checked={onlyActivated} onChange={setOnlyActivated} />
          <Toggle label="Show only states with conflicts" checked={onlyConflicts} onChange={setOnlyConflicts} />
          <Toggle label="Show only stale states" checked={onlyStale} onChange={setOnlyStale} />
        </div>
      </div>
    </section>
  );
}

function StateList({ states, selectedStateId, setSelectedStateId }) {
  return (
    <aside className="rounded-xl border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-base font-semibold text-slate-950">States</h2>
      </div>
      <div className="max-h-[820px] overflow-y-auto p-3">
        {states.length ? (
          states.map((state) => (
            <button
              key={state.id}
              type="button"
              onClick={() => setSelectedStateId(state.id)}
              className={`mb-2 w-full rounded-xl border p-4 text-left transition focus:outline-none focus:ring-4 focus:ring-blue-100 ${
                selectedStateId === state.id
                  ? "border-blue-300 bg-blue-50"
                  : "border-slate-200 bg-white hover:bg-slate-50"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-slate-950">
                    {state.name}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {state.category} - {state.displayValue}
                  </p>
                </div>
                {state.activated ? (
                  <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                    Activated
                  </span>
                ) : null}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <StatusBadge label={state.status} />
                <StatusBadge label={state.supportStatus} />
              </div>
              <dl className="mt-3 grid gap-2 text-xs text-slate-600">
                <InfoRow label="Updated" value={state.updatedAt} />
                <InfoRow label="Evidence" value={state.evidenceIds.length} />
                <InfoRow label="Dependencies" value={state.upstreamDependencyIds.length + state.downstreamDependencyIds.length} />
              </dl>
            </button>
          ))
        ) : (
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
            <p className="text-sm font-semibold text-slate-950">
              No states match the selected filters
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}

function StateDetails({
  state,
  showTechnical,
  setShowTechnical,
  patientId,
  onApproveReview,
  onRejectReview,
}) {
  if (!state) {
    return (
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <p className="text-sm text-slate-600">No state selected.</p>
      </section>
    );
  }

  return (
    <section className="space-y-5">
      <article className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">
              {state.id}
            </p>
            <h2 className="mt-1 text-xl font-semibold text-slate-950">
              {state.name}
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              Current value: <span className="font-semibold text-slate-950">{state.displayValue}</span>
              {state.unit ? ` ${state.unit}` : ""}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge label={state.status} />
            <StatusBadge label={state.supportStatus} />
          </div>
        </div>
        <div className="mt-5 grid gap-4 text-sm md:grid-cols-2">
          <InfoRow label="Category" value={state.category} />
          <InfoRow label="State version" value={state.stateVersion} />
          <InfoRow label="Effective from" value={state.effectiveFrom || "Not recorded"} />
          <InfoRow label="Effective until" value={state.effectiveUntil || "Not applicable"} />
          <InfoRow label="Last observed" value={state.lastObservedAt || "Not recorded"} />
          <InfoRow label="Last updated" value={state.updatedAt} />
          <InfoRow label="Next review" value={state.nextReviewDate || "Not scheduled"} />
          <InfoRow label="Trend" value={state.trend} />
        </div>
      </article>

      <article className="rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="text-base font-semibold text-slate-950">
          Support and Uncertainty
        </h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          {state.uncertaintySummary}
        </p>
        <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <InfoRow label="Source count" value={state.sourceCount} />
          <InfoRow label="Active evidence" value={state.activeEvidenceCount} />
          <InfoRow label="Conflicting evidence" value={state.conflictingEvidenceIds.length} />
          <InfoRow label="Pending evidence" value={state.pendingEvidenceCount} />
        </div>
        {state.status === "Contested" ? <ContestedStateNotice /> : null}
        {state.stale ? <StaleStateNotice patientId={patientId} /> : null}
        {state.reviewId ? (
          <ReviewDecisionPanel
            state={state}
            onApprove={() => onApproveReview(state.reviewId)}
            onReject={() => onRejectReview(state.reviewId)}
          />
        ) : null}
      </article>

      <article className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-center justify-between gap-4">
          <h3 className="text-base font-semibold text-slate-950">
            State History
          </h3>
          <History className="h-5 w-5 text-slate-400" aria-hidden="true" />
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
              <tr>
                <th className="py-2 pr-4">Effective</th>
                <th className="py-2 pr-4">Previous</th>
                <th className="py-2 pr-4">New</th>
                <th className="py-2 pr-4">Reason</th>
                <th className="py-2 pr-4">Version</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {csmHistory
                .filter((entry) => entry.stateId === state.id)
                .map((entry) => (
                  <tr key={entry.id}>
                    <td className="py-3 pr-4 text-slate-600">{entry.effectiveAt}</td>
                    <td className="py-3 pr-4 text-slate-800">{entry.previousValue}</td>
                    <td className="py-3 pr-4 font-medium text-slate-950">{entry.newValue}</td>
                    <td className="py-3 pr-4 text-slate-600">{entry.reason}</td>
                    <td className="py-3 pr-4 text-slate-600">{entry.stateVersion}</td>
                  </tr>
                ))}
            </tbody>
          </table>
          {!csmHistory.some((entry) => entry.stateId === state.id) ? (
            <p className="mt-3 text-sm text-slate-500">
              No previous versions are available for this state.
            </p>
          ) : null}
        </div>
      </article>

      <article className="rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="text-base font-semibold text-slate-950">
          Dependencies
        </h3>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <DependencyList title="Upstream states" items={state.upstreamDependencyIds} relation="influences selected state" />
          <DependencyList title="Downstream states" items={state.downstreamDependencyIds} relation="influenced by selected state" />
        </div>
      </article>

      <article className="rounded-xl border border-slate-200 bg-white p-5">
        <button
          type="button"
          onClick={() => setShowTechnical((value) => !value)}
          className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700"
        >
          <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
          {showTechnical ? "Hide" : "View"} State Technical Details
        </button>
        {showTechnical ? (
          <dl className="mt-4 grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm sm:grid-cols-2">
            <InfoRow label="Update operator" value={state.updateOperator} />
            <InfoRow label="Source observation IDs" value={state.evidenceIds.join(", ")} />
            <InfoRow label="Status reason" value={state.statusReason} />
            <InfoRow label="Serialization version" value={`csm-state-${state.stateVersion}`} />
          </dl>
        ) : null}
      </article>
    </section>
  );
}

function EvidenceAndLineagePanel({ evidenceItems, setSelectedEvidence, patientId }) {
  const groups = ["Supporting Evidence", "Conflicting Evidence", "Superseded Evidence", "Pending Review"];

  return (
    <aside className="space-y-5">
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-950">
          State Evidence
        </h2>
        <div className="mt-4 space-y-4">
          {groups.map((group) => {
            const items = evidenceItems.filter((item) => item.group === group);

            if (!items.length) {
              return null;
            }

            return (
              <div key={group}>
                <h3 className="text-sm font-semibold text-slate-700">{group}</h3>
                <div className="mt-2 space-y-2">
                  {items.map((item) => (
                    <article key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <p className="text-sm font-medium text-slate-950">
                        {item.sourceTitle}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {item.sourceType} - {item.effectiveDate}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-slate-600">
                        {item.excerpt}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <SmallAction label="Open Evidence Details" onClick={() => setSelectedEvidence(item)} />
                        <SmallAction label="Open Original Document" onClick={() => window.location.assign(`/patients/${patientId}/documents/doc-1?evidenceId=${item.id}`)} />
                        <SmallAction label="View Timeline Event" onClick={() => window.location.assign(`/patients/${patientId}/timeline`)} />
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-950">
          State Lineage
        </h2>
        <div className="mt-4 space-y-3">
          {csmLineage.map((node) => (
            <div key={`${node.type}-${node.identifier}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs font-semibold uppercase text-blue-700">
                {node.type}
              </p>
              <p className="mt-1 text-sm font-medium text-slate-950">
                {node.identifier}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {node.timestamp} - {node.actor} - {node.version}
              </p>
              <p className="mt-2 text-sm text-slate-600">{node.summary}</p>
            </div>
          ))}
        </div>
      </section>
    </aside>
  );
}

function ActivatedStatesPanel() {
  return (
    <section className="mt-6 rounded-xl border border-blue-200 bg-blue-50 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-blue-700">
            Activated for Question
          </p>
          <h2 className="mt-1 text-base font-semibold text-blue-950">
            {csmActivation.question}
          </h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-blue-900">
            {csmActivation.activationReason}
          </p>
        </div>
        <div className="rounded-lg border border-blue-200 bg-white px-4 py-3 text-sm text-blue-900">
          <p>{csmActivation.contextCost}</p>
          <p className="mt-1">Linked answer: {csmActivation.linkedAnswer}</p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {csmActivation.activationOrder.map((stateId, index) => (
          <span key={stateId} className="rounded-full border border-blue-200 bg-white px-3 py-1 text-xs font-medium text-blue-800">
            {index + 1}. {stateId}
          </span>
        ))}
      </div>
    </section>
  );
}

function AvailabilityState({ availability, patientId }) {
  const messages = {
    "CSM Processing": "Computational states are currently being updated from the latest patient evidence.",
    "CSM Out of Sync": "The CSM state version is behind the current patient memory version.",
    "CSM Failed": "The last CSM update failed. Retry processing after checking the source evidence.",
    "CSM Not Enabled": "Computational State Memory is not enabled for this patient workspace.",
    "CSM Not Initialized": "No persisted computational states exist yet. Sync CSM after adding patient information, uploading documents, or completing a chat.",
  };

  return (
    <section className="mt-6 rounded-xl border border-slate-200 bg-white p-6">
      <div className="flex gap-3">
        <AlertCircle className="mt-0.5 h-5 w-5 text-amber-700" aria-hidden="true" />
        <div>
          <h2 className="text-base font-semibold text-slate-950">
            {availability}
          </h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {messages[availability]}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <SmallAction label="Return to Overview" onClick={() => window.location.assign(`/patients/${patientId}`)} />
            <SmallAction label="Retry Processing" />
          </div>
        </div>
      </div>
    </section>
  );
}

function ReviewDecisionPanel({ state, onApprove, onReject }) {
  return (
    <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-4">
      <p className="text-sm font-semibold text-blue-900">
        Conversation proposal awaiting review
      </p>
      <p className="mt-2 text-sm leading-6 text-blue-900">
        This item came from chat evidence and has not been written into the
        permanent computational state. Approving it stores the proposed fact as
        a CSM state; rejecting it keeps the source evidence but removes the
        pending state proposal.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <SmallAction label={`Approve ${state.name}`} onClick={onApprove} />
        <SmallAction label="Reject Proposal" onClick={onReject} />
      </div>
    </div>
  );
}

function ContestedStateNotice() {
  return (
    <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4">
      <p className="text-sm font-semibold text-red-800">
        Conflicting Evidence
      </p>
      <ul className="mt-2 space-y-2 text-sm leading-6 text-red-800">
        <li>One source supports the current state.</li>
        <li>Another source conflicts with the current state.</li>
      </ul>
      <div className="mt-3 flex flex-wrap gap-2">
        <SmallAction label="Review Evidence" />
        <SmallAction label="Add Clarifying Information" />
        <SmallAction label="Mark for Review" />
      </div>
    </div>
  );
}

function StaleStateNotice({ patientId }) {
  return (
    <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
      <p className="text-sm font-semibold text-amber-800">
        State may be outdated
      </p>
      <p className="mt-2 text-sm leading-6 text-amber-800">
        No recent supporting evidence has updated this state within the
        configured freshness period.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <SmallAction label="View Last Evidence" />
        <SmallAction label="Add Patient Information" onClick={() => window.location.assign(`/patients/${patientId}/information`)} />
        <SmallAction label="Upload Document" onClick={() => window.location.assign(`/patients/${patientId}/documents`)} />
      </div>
    </div>
  );
}

function EvidenceDrawer({ evidence, onClose, patientId }) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-950/30" role="dialog" aria-modal="true">
      <div className="ml-auto flex h-full w-full max-w-xl flex-col bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">
              Evidence Details
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-950">
              {evidence.sourceTitle}
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
          <StatusBadge label={evidence.evidenceStatus} />
          <p className="text-sm leading-6 text-slate-700">{evidence.excerpt}</p>
          <dl className="grid gap-3 text-sm">
            <InfoRow label="Source type" value={evidence.sourceType} />
            <InfoRow label="Effective date" value={evidence.effectiveDate} />
            <InfoRow label="Verification" value={evidence.verification} />
            <InfoRow label="Contribution" value={evidence.contribution} />
          </dl>
          <div className="flex flex-wrap gap-2">
            <SmallAction label="Open Original Document" onClick={() => window.location.assign(`/patients/${patientId}/documents/doc-1?evidenceId=${evidence.id}`)} />
            <SmallAction label="View Timeline Event" onClick={() => window.location.assign(`/patients/${patientId}/timeline`)} />
          </div>
        </div>
      </div>
    </div>
  );
}

function CsmSkeleton() {
  return (
    <div className="mt-6 grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)_360px]">
      {[1, 2, 3].map((item) => (
        <div key={item} className="h-96 rounded-xl border border-slate-200 bg-white p-5">
          <div className="h-4 w-32 rounded bg-slate-200" />
          <div className="mt-4 h-5 w-3/4 rounded bg-slate-200" />
          <div className="mt-3 h-4 w-full rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}

function WorkspaceHeader({ patientId }) {
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
            <p className="text-xs text-slate-500">Computational state memory</p>
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

function PatientContext() {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">
            Patient: {csmPatient.displayName} - {csmPatient.systemPatientId}
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {csmPatient.age} years, {csmPatient.sex}. Primary condition:
            {" "}
            {csmPatient.primaryCondition}
          </p>
        </div>
        <div className="grid gap-2 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 sm:grid-cols-2">
          <p>Patient memory version: {csmPatient.memoryVersion}</p>
          <p>Last updated: {csmPatient.lastUpdated}</p>
        </div>
      </div>
    </section>
  );
}

function DependencyList({ title, items, relation }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <h4 className="text-sm font-semibold text-slate-950">{title}</h4>
      <div className="mt-3 space-y-2">
        {items.length ? (
          items.map((item) => (
            <div key={item} className="flex items-center gap-2 text-sm text-slate-600">
              <GitBranch className="h-4 w-4 text-blue-700" aria-hidden="true" />
              <span>{item}</span>
              <span className="text-slate-400">-</span>
              <span>{relation}</span>
            </div>
          ))
        ) : (
          <p className="text-sm text-slate-500">No dependencies recorded.</p>
        )}
      </div>
    </div>
  );
}

function FilterSelect({ label, value, onChange, options }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={inputClass()}
      >
        {options.map((option) => (
          <option key={option}>{option}</option>
        ))}
      </select>
    </label>
  );
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700">
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

function SmallAction({ label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-9 items-center justify-center rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
    >
      {label}
    </button>
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

function StatusBadge({ label }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${statusStyles[label] || statusStyles.ActiveEvidence}`}>
      {label}
    </span>
  );
}

function filterStates(states, filters) {
  const query = filters.searchTerm.trim().toLowerCase();

  return states
    .filter((state) => !query || `${state.name} ${state.displayValue}`.toLowerCase().includes(query))
    .filter((state) => filters.category === "All" || state.category === filters.category)
    .filter((state) => filters.stateStatus === "All" || state.status === filters.stateStatus)
    .filter((state) => filters.supportStatus === "All" || state.supportStatus === filters.supportStatus)
    .filter((state) => filters.evidenceFilter === "All" || (filters.evidenceFilter === "Has evidence" ? state.evidenceIds.length > 0 : state.evidenceIds.length === 0))
    .filter((state) => !filters.onlyActivated || state.activated)
    .filter((state) => !filters.onlyConflicts || state.conflictingEvidenceIds.length > 0)
    .filter((state) => !filters.onlyStale || state.stale)
    .filter((state) => {
      if (filters.updatedFilter === "All") {
        return true;
      }

      return state.updatedAt.includes("July 2026");
    });
}

function inputClass(extra = "") {
  return `h-11 w-full rounded-lg border border-slate-300 bg-white px-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-700 focus:ring-4 focus:ring-blue-100 ${extra}`;
}

function getPatientId() {
  return window.location.pathname.split("/")[2] || csmPatient.id;
}
