import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Database,
  Loader2,
  RefreshCcw,
  ShieldCheck,
} from "lucide-react";

import { getLlmStatus, listMemorySystems } from "../../services/memorySystemsApi";

export function MemorySystemsPage() {
  const [systems, setSystems] = useState([]);
  const [llmStatus, setLlmStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const counts = useMemo(() => {
    return systems.reduce(
      (total, system) => ({
        all: total.all + 1,
        retrieval: total.retrieval + Number(system.capability_status.retrieval === "available"),
        llm: total.llm + Number(system.requires_llm),
        external: total.external + Number(system.requires_external_provider),
      }),
      { all: 0, retrieval: 0, llm: 0, external: 0 },
    );
  }, [systems]);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    setError(null);

    try {
      const [systemData, llmData] = await Promise.all([
        listMemorySystems(),
        getLlmStatus(),
      ]);
      setSystems(systemData);
      setLlmStatus(llmData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8">
          <button
            type="button"
            onClick={() => window.location.assign("/patients")}
            className="flex items-center gap-3 rounded-lg focus:outline-none focus:ring-4 focus:ring-blue-100"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-700 text-white">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="hidden text-left sm:block">
              <p className="text-sm font-semibold text-slate-950">Medical Memory Platform</p>
              <p className="text-xs text-slate-500">Memory-system registry</p>
            </div>
          </button>
          <button
            type="button"
            onClick={() => window.location.assign("/patients")}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Patients
          </button>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-sm font-medium text-slate-500">Backend registry</p>
              <h1 className="mt-2 text-2xl font-semibold text-slate-950">Memory Systems</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                Registry of supported memory architectures and current provider capabilities.
              </p>
            </div>
            <button
              type="button"
              onClick={load}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
              Refresh
            </button>
          </div>
        </section>

        <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Metric label="Systems" value={counts.all} />
          <Metric label="Retrieval available" value={counts.retrieval} />
          <Metric label="Require LLM" value={counts.llm} />
          <Metric label="LLM provider" value={formatType(llmStatus?.status ?? "unknown")} />
        </section>

        {llmStatus ? (
          <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-base font-semibold text-slate-950">Common Answer Provider</h2>
                <p className="mt-1 text-sm text-slate-600">
                  {llmStatus.provider} - {llmStatus.model} - prompt v{llmStatus.prompt_version}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <StatusBadge status={llmStatus.status} />
                <StatusBadge status={llmStatus.api_key_configured ? "key_configured" : "key_missing"} />
                <StatusBadge status={llmStatus.data_egress_mode} />
              </div>
            </div>
          </section>
        ) : null}

        {error ? (
          <div className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="mt-6 rounded-xl border border-slate-200 bg-white px-6 py-12 text-center text-sm text-slate-500">
            Loading memory systems...
          </div>
        ) : null}

        {!loading && !error ? (
          <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {systems.map((system) => (
              <SystemCard key={system.system_type} system={system} />
            ))}
          </section>
        ) : null}
      </main>
    </div>
  );
}

function SystemCard({ system }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-950">{system.display_name}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">{system.description}</p>
        </div>
        <Database className="h-5 w-5 shrink-0 text-blue-700" />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <StatusBadge status={system.capability_status.ingestion} />
        <StatusBadge status={system.capability_status.retrieval} />
        <StatusBadge status={system.capability_status.provider} />
      </div>

      <dl className="mt-5 grid gap-3 text-sm">
        <InfoRow label="System type" value={system.system_type} />
        <InfoRow label="Storage" value={system.storage_summary} />
        <InfoRow label="Modes" value={system.supported_retrieval_modes.join(", ")} />
        <InfoRow label="Embeddings" value={system.capability_status.embeddings} />
        <InfoRow label="Generation" value={system.capability_status.answer_generation} />
      </dl>
    </article>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{formatType(value)}</dd>
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

function badgeTone(status = "") {
  if (["ready", "available", "completed"].includes(status)) {
    return "border-green-200 bg-green-50 text-green-700";
  }

  if (["requires_llm", "requires_embeddings", "provider_not_configured", "provider_not_installed", "not_ready"].includes(status)) {
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
