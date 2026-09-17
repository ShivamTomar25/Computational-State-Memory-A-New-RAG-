import { useMemo, useState } from "react";
import {
  Archive,
  Copy,
  Download,
  Pause,
  Play,
  Plus,
} from "lucide-react";
import {
  EmptyState,
  InfoRow,
  Modal,
  PageHero,
  PlatformShell,
  PrimaryButton,
  SecondaryButton,
  SelectField,
  StatePanel,
  StatusBadge,
  TableShell,
  TextField,
  go,
  inputClass,
} from "../platform_shared/PlatformShell";
import { experimentRuns, experiments } from "../platform_shared/platformService";

const tabs = ["Overview", "Configuration", "Runs", "Results", "Evaluations", "Failures", "Export"];

export function ExperimentManagementPage() {
  const path = window.location.pathname;
  const routeId = path.split("/")[3] || "";
  const isNew = path.endsWith("/new");
  const [items, setItems] = useState(experiments);
  const [demoState, setDemoState] = useState("Ready");
  const [statusFilter, setStatusFilter] = useState("All");
  const [activeTab, setActiveTab] = useState("Overview");
  const [formError, setFormError] = useState("");
  const [draft, setDraft] = useState({
    name: "",
    researchQuestion: "",
    hypothesis: "",
    architectures: "Long Context, Rolling Summary, Dense RAG, Hybrid RAG, GraphRAG, HippoRAG, CSM",
    cohort: "",
    questionSet: "",
    memoryPolicy: "Use latest synchronized version",
    modelConfiguration: "Default clinical response model",
    retrievalConfiguration: "Default patient-scoped retrieval",
    randomSeed: "42",
    repetitions: "1",
    evaluationStrategy: "Clinician review",
    notes: "",
  });

  const selectedExperiment = items.find((item) => item.id === routeId) || items[0];
  const filteredItems = useMemo(
    () => items.filter((item) => statusFilter === "All" || item.status === statusFilter),
    [items, statusFilter],
  );

  function updateStatus(id, status) {
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, status } : item)),
    );
  }

  function duplicateExperiment(experiment) {
    const copy = {
      ...experiment,
      id: `exp-${Date.now()}`,
      name: `${experiment.name} Copy`,
      status: "Draft",
      progress: "0%",
    };
    setItems((current) => [copy, ...current]);
  }

  function createExperiment(event) {
    event.preventDefault();

    if (!draft.name.trim() || !draft.researchQuestion.trim()) {
      setFormError("Experiment name and research question are required.");
      return;
    }

    const experiment = {
      id: `exp-${Date.now()}`,
      name: draft.name.trim(),
      description: draft.researchQuestion.trim(),
      status: "Draft",
      architectures: draft.architectures.split(",").map((item) => item.trim()).filter(Boolean),
      cohort: draft.cohort,
      questionSet: draft.questionSet,
      memoryPolicy: draft.memoryPolicy,
      createdBy: "Current doctor",
      createdDate: "Just now",
      progress: "0%",
    };

    setItems((current) => [experiment, ...current]);
    setFormError("");
    go(`/research/experiments/${experiment.id}`);
  }

  return (
    <PlatformShell sectionLabel="Experiment management">
      {isNew ? (
        <CreateExperimentView
          draft={draft}
          setDraft={setDraft}
          formError={formError}
          createExperiment={createExperiment}
        />
      ) : routeId ? (
        <ExperimentDetailView
          experiment={selectedExperiment}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          updateStatus={updateStatus}
        />
      ) : (
        <ExperimentListView
          items={filteredItems}
          demoState={demoState}
          setDemoState={setDemoState}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          updateStatus={updateStatus}
          duplicateExperiment={duplicateExperiment}
        />
      )}
    </PlatformShell>
  );
}

function ExperimentListView({
  items,
  demoState,
  setDemoState,
  statusFilter,
  setStatusFilter,
  updateStatus,
  duplicateExperiment,
}) {
  return (
    <>
      <PageHero
        eyebrow="Research"
        title="Experiment Management"
        description="Create, run, review, and export controlled architecture experiments."
        actions={
          <PrimaryButton onClick={() => go("/research/experiments/new")}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            New Experiment
          </PrimaryButton>
        }
      />

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField label="Status" value={statusFilter} onChange={setStatusFilter} options={["All", "Draft", "Ready", "Running", "Paused", "Complete", "Failed", "Archived"]} />
          <SelectField label="Demo state" value={demoState} onChange={setDemoState} options={["Ready", "Loading", "Empty", "Error", "Unauthorized"]} />
        </div>
      </section>

      {demoState === "Unauthorized" ? (
        <div className="mt-6">
          <StatePanel title="Access denied" text="This account is not authorized to manage experiments." />
        </div>
      ) : null}
      {demoState === "Error" ? (
        <div className="mt-6">
          <StatePanel title="Experiment request failed" text="Experiment data could not be loaded." />
        </div>
      ) : null}
      {demoState === "Empty" ? (
        <div className="mt-6">
          <EmptyState title="No experiments found" text="Create an experiment to compare memory architectures under controlled conditions." />
        </div>
      ) : null}
      {demoState === "Loading" ? <ExperimentSkeleton /> : null}

      {demoState === "Ready" ? (
        <section className="mt-6">
          <TableShell caption="Experiments" columns={["Experiment", "Status", "Architectures", "Cohort", "Question Set", "Memory Policy", "Created", "Progress", "Actions"]}>
            {items.map((experiment) => (
              <tr key={experiment.id} className="hover:bg-slate-50">
                <td className="px-5 py-4">
                  <p className="text-sm font-semibold text-slate-950">{experiment.name}</p>
                  <p className="mt-1 text-xs text-slate-500">{experiment.description}</p>
                </td>
                <td className="px-5 py-4"><StatusBadge label={experiment.status} /></td>
                <td className="px-5 py-4 text-sm text-slate-600">{experiment.architectures.join(", ")}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{experiment.cohort}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{experiment.questionSet}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{experiment.memoryPolicy}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{experiment.createdBy}, {experiment.createdDate}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{experiment.progress}</td>
                <td className="px-5 py-4">
                  <div className="flex flex-wrap gap-2">
                    <SecondaryButton onClick={() => go(`/research/experiments/${experiment.id}`)}>Open</SecondaryButton>
                    <SecondaryButton onClick={() => duplicateExperiment(experiment)}><Copy className="h-4 w-4" aria-hidden="true" />Duplicate</SecondaryButton>
                    <SecondaryButton onClick={() => updateStatus(experiment.id, "Running")}><Play className="h-4 w-4" aria-hidden="true" />Start</SecondaryButton>
                    <SecondaryButton onClick={() => updateStatus(experiment.id, "Paused")}><Pause className="h-4 w-4" aria-hidden="true" />Pause</SecondaryButton>
                    <SecondaryButton onClick={() => updateStatus(experiment.id, "Archived")}><Archive className="h-4 w-4" aria-hidden="true" />Archive</SecondaryButton>
                  </div>
                </td>
              </tr>
            ))}
          </TableShell>
        </section>
      ) : null}
    </>
  );
}

function CreateExperimentView({ draft, setDraft, formError, createExperiment }) {
  function update(field, value) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  return (
    <>
      <PageHero
        eyebrow="Research"
        title="Create Experiment"
        description="Define a controlled architecture experiment. API keys and secrets are not stored in this form."
      />
      <form onSubmit={createExperiment} className="mt-6 rounded-xl border border-slate-200 bg-white">
        <div className="grid gap-5 p-6 md:grid-cols-2">
          <TextField label="Experiment name" value={draft.name} onChange={(value) => update("name", value)} placeholder="Medication conflict comparison" />
          <TextField label="Research question" value={draft.researchQuestion} onChange={(value) => update("researchQuestion", value)} placeholder="How do systems handle contested medication evidence?" />
          <TextField label="Hypothesis" value={draft.hypothesis} onChange={(value) => update("hypothesis", value)} placeholder="CSM may surface conflicts more explicitly." />
          <TextField label="Selected architectures" value={draft.architectures} onChange={(value) => update("architectures", value)} />
          <TextField label="Patient cohort" value={draft.cohort} onChange={(value) => update("cohort", value)} />
          <TextField label="Question dataset" value={draft.questionSet} onChange={(value) => update("questionSet", value)} />
          <SelectField label="Memory-version policy" value={draft.memoryPolicy} onChange={(value) => update("memoryPolicy", value)} options={["Use latest synchronized version", "Lock memory version per run", "Require exact version match"]} />
          <TextField label="Model configuration" value={draft.modelConfiguration} onChange={(value) => update("modelConfiguration", value)} />
          <TextField label="Retrieval configuration" value={draft.retrievalConfiguration} onChange={(value) => update("retrievalConfiguration", value)} />
          <TextField label="Random seed" value={draft.randomSeed} onChange={(value) => update("randomSeed", value)} />
          <TextField label="Repetitions per question" value={draft.repetitions} onChange={(value) => update("repetitions", value)} />
          <SelectField label="Evaluation strategy" value={draft.evaluationStrategy} onChange={(value) => update("evaluationStrategy", value)} options={["Clinician review", "Citation audit", "Research rubric", "Manual review only"]} />
          <label className="block md:col-span-2">
            <span className="mb-2 block text-sm font-medium text-slate-700">Notes</span>
            <textarea
              value={draft.notes}
              onChange={(event) => update("notes", event.target.value)}
              rows={4}
              className={`${inputClass()} h-auto py-3`}
            />
          </label>
        </div>
        {formError ? <p className="px-6 pb-4 text-sm font-medium text-red-700">{formError}</p> : null}
        <footer className="flex justify-end gap-3 border-t border-slate-200 bg-slate-50 px-6 py-4">
          <SecondaryButton onClick={() => go("/research/experiments")}>Cancel</SecondaryButton>
          <PrimaryButton type="submit">Create Experiment</PrimaryButton>
        </footer>
      </form>
    </>
  );
}

function ExperimentDetailView({ experiment, activeTab, setActiveTab, updateStatus }) {
  return (
    <>
      <PageHero
        eyebrow="Experiment detail"
        title={experiment.name}
        description={experiment.description}
        actions={
          <>
            <SecondaryButton onClick={() => updateStatus(experiment.id, "Running")}><Play className="h-4 w-4" aria-hidden="true" />Start</SecondaryButton>
            <SecondaryButton onClick={() => updateStatus(experiment.id, "Paused")}><Pause className="h-4 w-4" aria-hidden="true" />Pause</SecondaryButton>
            <SecondaryButton><Download className="h-4 w-4" aria-hidden="true" />Export</SecondaryButton>
          </>
        }
      />
      <nav className="mt-6 overflow-x-auto border-b border-slate-200">
        <div className="flex min-w-max gap-1">
          {tabs.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`h-11 border-b-2 px-4 text-sm font-medium ${
                activeTab === tab
                  ? "border-blue-700 text-blue-700"
                  : "border-transparent text-slate-600 hover:text-slate-950"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </nav>
      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <ExperimentTab experiment={experiment} activeTab={activeTab} />
      </section>
    </>
  );
}

function ExperimentTab({ experiment, activeTab }) {
  if (activeTab === "Runs") {
    return (
      <TableShell caption="Experiment runs" columns={["Patient", "Question", "Architecture", "Status", "Latency", "Tokens", "Cost", "Memory Version", "Error"]}>
        {experimentRuns.map((run) => (
          <tr key={run.id}>
            <td className="px-5 py-4 text-sm text-slate-600">{run.patient}</td>
            <td className="px-5 py-4 text-sm text-slate-600">{run.question}</td>
            <td className="px-5 py-4 text-sm text-slate-600">{run.architecture}</td>
            <td className="px-5 py-4"><StatusBadge label={run.status} /></td>
            <td className="px-5 py-4 text-sm text-slate-600">{run.latency}</td>
            <td className="px-5 py-4 text-sm text-slate-600">{run.tokens}</td>
            <td className="px-5 py-4 text-sm text-slate-600">{run.cost}</td>
            <td className="px-5 py-4 text-sm text-slate-600">{run.memoryVersion}</td>
            <td className="px-5 py-4 text-sm text-slate-600">{run.error}</td>
          </tr>
        ))}
      </TableShell>
    );
  }

  if (activeTab === "Results") {
    return (
      <div className="space-y-4">
        <p className="text-sm leading-6 text-slate-600">
          Result comparison reuses the same evidence-grounded fields as the
          Compare Systems workflow. No winner badge is applied automatically.
        </p>
        <TableShell caption="Result comparison" columns={["Architecture", "Question", "Support", "Citation Coverage", "Latency"]}>
          {experimentRuns.filter((run) => run.status === "Complete").map((run) => (
            <tr key={run.id}>
              <td className="px-5 py-4 text-sm text-slate-600">{run.architecture}</td>
              <td className="px-5 py-4 text-sm text-slate-600">{run.question}</td>
              <td className="px-5 py-4"><StatusBadge label="Active" /></td>
              <td className="px-5 py-4 text-sm text-slate-600">Available</td>
              <td className="px-5 py-4 text-sm text-slate-600">{run.latency}</td>
            </tr>
          ))}
        </TableShell>
      </div>
    );
  }

  if (activeTab === "Failures") {
    return (
      <TableShell caption="Experiment failures" columns={["Run", "Architecture", "Error", "Retryable"]}>
        {experimentRuns.filter((run) => run.status === "Failed").map((run) => (
          <tr key={run.id}>
            <td className="px-5 py-4 text-sm text-slate-600">{run.id}</td>
            <td className="px-5 py-4 text-sm text-slate-600">{run.architecture}</td>
            <td className="px-5 py-4 text-sm text-slate-600">{run.error}</td>
            <td className="px-5 py-4 text-sm text-slate-600">Yes</td>
          </tr>
        ))}
      </TableShell>
    );
  }

  if (activeTab === "Export") {
    return (
      <ModalPreview />
    );
  }

  return (
    <dl className="grid gap-3 text-sm md:grid-cols-2">
      <InfoRow label="Status" value={experiment.status} />
      <InfoRow label="Architectures" value={experiment.architectures.join(", ")} />
      <InfoRow label="Patient cohort" value={experiment.cohort} />
      <InfoRow label="Question set" value={experiment.questionSet} />
      <InfoRow label="Memory-version policy" value={experiment.memoryPolicy} />
      <InfoRow label="Created by" value={experiment.createdBy} />
      <InfoRow label="Created date" value={experiment.createdDate} />
      <InfoRow label="Progress" value={experiment.progress} />
    </dl>
  );
}

function ModalPreview() {
  const [showModal, setShowModal] = useState(false);

  return (
    <div>
      <p className="text-sm leading-6 text-slate-600">
        Export supports JSON and CSV now. PDF report generation is a backend placeholder.
      </p>
      <div className="mt-4">
        <PrimaryButton onClick={() => setShowModal(true)}>Prepare Export</PrimaryButton>
      </div>
      {showModal ? (
        <Modal title="Experiment Export" onClose={() => setShowModal(false)}>
          <p className="text-sm text-slate-600">
            Export request queued. Download links must be short-lived and signed by the backend.
          </p>
          <div className="mt-5 flex justify-end">
            <PrimaryButton onClick={() => setShowModal(false)}>Close</PrimaryButton>
          </div>
        </Modal>
      ) : null}
    </div>
  );
}

function ExperimentSkeleton() {
  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
      <div className="h-4 w-40 rounded bg-slate-200" />
      <div className="mt-4 h-5 w-2/3 rounded bg-slate-200" />
    </div>
  );
}
