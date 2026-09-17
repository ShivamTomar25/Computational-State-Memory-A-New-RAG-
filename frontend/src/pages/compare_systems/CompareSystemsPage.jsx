import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Database,
  FileText,
  GitCompareArrows,
  Loader2,
  MessageSquareText,
  Play,
  RefreshCcw,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";

import { getPatient } from "../patient_shared/patientApi";
import {
  initializeAllMemorySystems,
  initializeMemorySystem,
  listMemorySystems,
  listPatientMemorySystems,
  rebuildMemorySystem,
  syncMemorySystem,
} from "../../services/memorySystemsApi";

export function CompareSystemsPage() {
  const patientId = getPatientId();
  const [patient, setPatient] = useState(null);
  const [registry, setRegistry] = useState([]);
  const [systems, setSystems] = useState([]);
  const [runsSystem, setRunsSystem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionKey, setActionKey] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const cards = useMemo(() => {
    return registry.map((item) => {
      const instance = systems.find((system) => system.system_type === item.system_type);

      return {
        ...item,
        instance,
      };
    });
  }, [registry, systems]);

  useEffect(() => {
    load();
  }, [patientId]);

  async function load() {
    setLoading(true);
    setError(null);

    try {
      const [patientData, registryData, systemData] = await Promise.all([
        getPatient(patientId),
        listMemorySystems(),
        listPatientMemorySystems(patientId),
      ]);
      setPatient(patientData);
      setRegistry(registryData);
      setSystems(systemData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  async function runAction(label, systemType, action) {
    setActionKey(`${label}-${systemType}`);
    setError(null);
    setSuccess(null);

    try {
      await action();
      setSuccess(`${formatType(systemType)} ${label} completed.`);
      await load();
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setActionKey(null);
    }
  }

  function initialize(systemType) {
    return runAction("initialize", systemType, () => initializeMemorySystem(patientId, systemType));
  }

  async function initializeAll() {
    setActionKey("initialize-all");
    setError(null);
    setSuccess(null);

    try {
      const systemData = await initializeAllMemorySystems(patientId);
      setSystems(systemData);
      setSuccess("All patient memory systems initialized.");
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setActionKey(null);
    }
  }

  function sync(systemType) {
    return runAction("sync", systemType, () => syncMemorySystem(patientId, systemType, {}));
  }

  function rebuild(systemType) {
    const confirmed = window.confirm("Rebuild this memory-system index for the current patient?");

    if (!confirmed) {
      return;
    }

    return runAction("rebuild", systemType, () => rebuildMemorySystem(patientId, systemType));
  }

  if (loading) {
    return <PageShell patient={patient} patientId={patientId}>Loading memory systems...</PageShell>;
  }

  return (
    <PageShell patient={patient} patientId={patientId}>
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">
              {patient?.full_name ?? "Patient"} - {patient?.patient_code ?? patientId}
            </p>
            <h1 className="mt-2 text-2xl font-semibold text-slate-950">
              Compare Memory Systems
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Initialize, synchronize, and inspect retrieval-only memory baselines for the same patient-shared input snapshot.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={initializeAll}
              disabled={actionKey === "initialize-all"}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:opacity-60"
            >
              {actionKey === "initialize-all" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              Initialize All
            </button>
            <button
              type="button"
              onClick={load}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              <RefreshCcw className="h-4 w-4" />
              Refresh
            </button>
          </div>
        </div>
      </section>

      {error ? <Notice tone="error" message={error} /> : null}
      {success ? <Notice tone="success" message={success} /> : null}

      <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <SystemCard
            key={card.system_type}
            card={card}
            patientId={patientId}
            actionKey={actionKey}
            onInitialize={initialize}
            onSync={sync}
            onRebuild={rebuild}
            onRuns={setRunsSystem}
          />
        ))}
      </section>

      {runsSystem ? (
        <RunsDrawer
          patientId={patientId}
          system={runsSystem}
          onClose={() => setRunsSystem(null)}
        />
      ) : null}
    </PageShell>
  );
}

function PageShell({ patient, patientId, children }) {
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
              <p className="text-xs text-slate-500">{patient?.full_name ?? "Memory systems"}</p>
            </div>
          </button>
          <button
            type="button"
            onClick={() => window.location.assign(`/patients/${patientId}`)}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8">{children}</main>
    </div>
  );
}

function SystemCard({ card, patientId, actionKey, onInitialize, onSync, onRebuild, onRuns }) {
  const instance = card.instance;
  const status = instance?.status ?? "not_initialized";
  const sourceCounts = instance?.statistics?.source_counts ?? {};
  const stats = instance?.statistics ?? {};

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-950">{card.display_name}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">{card.description}</p>
        </div>
        <GitCompareArrows className="h-5 w-5 shrink-0 text-blue-700" />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <StatusBadge status={status} />
        <StatusBadge status={card.capability_status.answer_generation} />
        <StatusBadge status={card.capability_status.embeddings} />
      </div>

      <dl className="mt-5 grid gap-3 text-sm">
        <InfoRow label="Ingestion" value={capability(instance, card, "ingestion")} />
        <InfoRow label="Retrieval" value={capability(instance, card, "retrieval")} />
        <InfoRow label="LLM" value={capability(instance, card, "answer_generation")} />
        <InfoRow label="Patient sources" value={sourceCounts.patient_information ?? 0} />
        <InfoRow label="Document sources" value={sourceCounts.document ?? 0} />
        <InfoRow label="Private messages" value={sourceCounts.conversation ?? 0} />
        <InfoRow label="Last synced" value={formatDateTime(instance?.last_synced_at)} />
        <InfoRow label="Cutoff" value={formatDateTime(instance?.source_cutoff_time)} />
        <InfoRow label="Pipeline" value={instance?.pipeline_version ?? card.instance?.pipeline_version ?? "1"} />
        <InfoRow label="Storage" value={storageSummary(stats)} />
      </dl>

      {instance?.failure_reason ? (
        <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {instance.failure_reason}
        </p>
      ) : null}

      <div className="mt-5 flex flex-wrap gap-2">
        <ActionButton
          label="Initialize"
          loading={actionKey === `initialize-${card.system_type}`}
          onClick={() => onInitialize(card.system_type)}
        />
        <ActionButton
          label="Sync"
          disabled={!instance?.id}
          loading={actionKey === `sync-${card.system_type}`}
          onClick={() => onSync(card.system_type)}
        />
        <ActionButton
          label="Rebuild"
          disabled={!instance?.id}
          loading={actionKey === `rebuild-${card.system_type}`}
          onClick={() => onRebuild(card.system_type)}
        />
        <ActionButton
          label="Open"
          disabled={!instance?.id}
          onClick={() => window.location.assign(`/patients/${patientId}/systems/${card.system_type}`)}
        />
        <ActionButton
          label="Runs"
          disabled={!instance?.id}
          onClick={() => onRuns(card)}
        />
      </div>
    </article>
  );
}

function RunsDrawer({ patientId, system, onClose }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    import("../../services/memorySystemsApi")
      .then(({ listIngestionRuns }) => listIngestionRuns(patientId, system.system_type))
      .then(setRuns)
      .catch((runError) => setError(runError.message))
      .finally(() => setLoading(false));
  }, [patientId, system.system_type]);

  return (
    <div className="fixed inset-0 z-40 bg-slate-950/30">
      <div className="ml-auto h-full w-full max-w-xl overflow-y-auto bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">{system.display_name} Runs</h2>
            <p className="mt-1 text-sm text-slate-500">Ingestion history for this patient and system.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700">
            Close
          </button>
        </div>
        {loading ? <p className="mt-6 text-sm text-slate-500">Loading runs...</p> : null}
        {error ? <Notice tone="error" message={error} /> : null}
        <div className="mt-6 space-y-3">
          {runs.map((run) => (
            <div key={run.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3">
                <StatusBadge status={run.status} />
                <span className="text-xs text-slate-500">{formatDateTime(run.created_at)}</span>
              </div>
              <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <InfoRow label="Mode" value={run.mode} />
                <InfoRow label="Sources" value={run.source_count} />
                <InfoRow label="Processed" value={run.processed_count} />
                <InfoRow label="Failed" value={run.failed_count} />
              </dl>
            </div>
          ))}
          {!runs.length && !loading ? <p className="text-sm text-slate-500">No ingestion runs yet.</p> : null}
        </div>
      </div>
    </div>
  );
}

function ActionButton({ label, disabled, loading, onClick }) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      onClick={onClick}
      className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : iconFor(label)}
      {label}
    </button>
  );
}

function iconFor(label) {
  if (label === "Initialize") {
    return <Play className="h-4 w-4" />;
  }

  if (label === "Sync") {
    return <RefreshCcw className="h-4 w-4" />;
  }

  if (label === "Rebuild") {
    return <RotateCcw className="h-4 w-4" />;
  }

  if (label === "Open") {
    return <Database className="h-4 w-4" />;
  }

  return <FileText className="h-4 w-4" />;
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value || "Not set"}</dd>
    </div>
  );
}

function StatusBadge({ status }) {
  const tone = badgeTone(status);

  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${tone}`}>
      {formatType(status)}
    </span>
  );
}

function Notice({ tone, message }) {
  const styles = {
    success: "border-green-200 bg-green-50 text-green-700",
    error: "border-red-200 bg-red-50 text-red-700",
  };

  return (
    <div className={`mt-6 rounded-lg border px-4 py-3 text-sm ${styles[tone]}`}>
      {message}
    </div>
  );
}

function capability(instance, card, key) {
  return formatType((instance?.capability_status ?? card.capability_status)?.[key]);
}

function storageSummary(stats) {
  const entries = Object.entries(stats).filter(([, value]) => typeof value !== "object");

  if (!entries.length) {
    return "No index yet";
  }

  return entries.slice(0, 2).map(([key, value]) => `${formatType(key)}: ${value}`).join(", ");
}

function badgeTone(status = "") {
  if (["ready", "available", "completed"].includes(status)) {
    return "border-green-200 bg-green-50 text-green-700";
  }

  if (["requires_llm", "requires_embeddings", "provider_not_configured", "provider_not_installed", "not_ready", "not_initialized"].includes(status)) {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }

  if (["failed", "unavailable"].includes(status)) {
    return "border-red-200 bg-red-50 text-red-700";
  }

  return "border-slate-200 bg-slate-50 text-slate-700";
}

function formatType(value = "") {
  if (!value) {
    return "Not set";
  }

  return String(value).replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
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

function getPatientId() {
  return window.location.pathname.split("/")[2] || "";
}
