import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Loader2, ShieldCheck } from "lucide-react";

import { CitationAuditViewer } from "../../components/evaluation/CitationAuditViewer";
import { ClaimAuditViewer } from "../../components/evaluation/ClaimAuditViewer";
import { ContradictionViewer } from "../../components/evaluation/ContradictionViewer";
import { CorrectionRecoveryViewer } from "../../components/evaluation/CorrectionRecoveryViewer";
import { CsmStateTraceViewer } from "../../components/evaluation/CsmStateTraceViewer";
import { DatasetSelector } from "../../components/evaluation/DatasetSelector";
import { ExperimentConfigurator } from "../../components/evaluation/ExperimentConfigurator";
import { ExperimentProgress } from "../../components/evaluation/ExperimentProgress";
import { ExportControls } from "../../components/evaluation/ExportControls";
import { HallucinationViewer } from "../../components/evaluation/HallucinationViewer";
import { HumanReviewQueue } from "../../components/evaluation/HumanReviewQueue";
import { MetricRankingTable } from "../../components/evaluation/MetricRankingTable";
import { MetricSelector } from "../../components/evaluation/MetricSelector";
import { MetricSummaryCard } from "../../components/evaluation/MetricSummaryCard";
import { RetrievalTraceViewer } from "../../components/evaluation/RetrievalTraceViewer";
import { StatisticalResults } from "../../components/evaluation/StatisticalResults";
import { SystemComparisonTable } from "../../components/evaluation/SystemComparisonTable";
import { SystemSelector } from "../../components/evaluation/SystemSelector";
import { TemporalTimelineViewer } from "../../components/evaluation/TemporalTimelineViewer";
import {
  createEvaluationExperiment,
  createEvaluationExport,
  getEvaluationCitations,
  getEvaluationClaims,
  getEvaluationHallucinations,
  getEvaluationProgress,
  getEvaluationResults,
  listEvaluationDatasets,
  listEvaluationExperiments,
  listEvaluationMetrics,
  startEvaluationExperiment,
} from "../../services/evaluationApi";

export function EvaluationDashboardPage() {
  const [datasets, setDatasets] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [experiments, setExperiments] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [selectedExperimentId, setSelectedExperimentId] = useState("");
  const [progress, setProgress] = useState(null);
  const [results, setResults] = useState(null);
  const [audits, setAudits] = useState({ claims: [], citations: [], hallucinations: [] });
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const selectedExperiment = useMemo(
    () => experiments.find((experiment) => experiment.id === selectedExperimentId),
    [experiments, selectedExperimentId],
  );

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    setError(null);

    try {
      const [datasetData, metricData, experimentData] = await Promise.all([
        listEvaluationDatasets(),
        listEvaluationMetrics(),
        listEvaluationExperiments(),
      ]);
      setDatasets(datasetData);
      setMetrics(metricData);
      setExperiments(experimentData);
      setSelectedDatasetId((current) => current || datasetData[0]?.id || "");
      setSelectedExperimentId((current) => current || experimentData[0]?.id || "");
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!selectedExperimentId) {
      setProgress(null);
      setResults(null);
      setAudits({ claims: [], citations: [], hallucinations: [] });
      return;
    }

    Promise.all([
      getEvaluationProgress(selectedExperimentId),
      getEvaluationResults(selectedExperimentId),
      getEvaluationClaims(selectedExperimentId),
      getEvaluationCitations(selectedExperimentId),
      getEvaluationHallucinations(selectedExperimentId),
    ])
      .then(([progressData, resultData, claimsData, citationsData, hallucinationsData]) => {
        setProgress(progressData);
        setResults(resultData);
        setAudits({
          claims: claimsData,
          citations: citationsData,
          hallucinations: hallucinationsData,
        });
      })
      .catch((loadError) => setError(loadError.message));
  }, [selectedExperimentId]);

  async function createExperiment() {
    if (!selectedDatasetId) {
      return;
    }

    setAction("create");
    setError(null);
    setNotice(null);

    try {
      const experiment = await createEvaluationExperiment({
        name: `Smoke evaluation ${new Date().toLocaleString("en-IN")}`,
        dataset_id: selectedDatasetId,
        profile: "smoke",
        configuration: {},
      });
      const experimentData = await listEvaluationExperiments();
      setExperiments(experimentData);
      setSelectedExperimentId(experiment.id);
      setNotice("Smoke experiment created.");
    } catch (createError) {
      setError(createError.message);
    } finally {
      setAction(null);
    }
  }

  async function startExperiment() {
    if (!selectedExperimentId) {
      return;
    }

    setAction("start");
    setError(null);
    setNotice(null);

    try {
      await startEvaluationExperiment(selectedExperimentId);
      const [progressData, resultData, experimentData] = await Promise.all([
        getEvaluationProgress(selectedExperimentId),
        getEvaluationResults(selectedExperimentId),
        listEvaluationExperiments(),
      ]);
      const [claimsData, citationsData, hallucinationsData] = await Promise.all([
        getEvaluationClaims(selectedExperimentId),
        getEvaluationCitations(selectedExperimentId),
        getEvaluationHallucinations(selectedExperimentId),
      ]);
      setProgress(progressData);
      setResults(resultData);
      setExperiments(experimentData);
      setAudits({
        claims: claimsData,
        citations: citationsData,
        hallucinations: hallucinationsData,
      });
      setNotice("Experiment runs prepared. Measured scores remain pending until the live runner completes.");
    } catch (startError) {
      setError(startError.message);
    } finally {
      setAction(null);
    }
  }

  async function exportResults(exportType) {
    if (!selectedExperimentId) {
      return;
    }

    setAction(`export-${exportType}`);
    setError(null);
    setNotice(null);

    try {
      await createEvaluationExport(selectedExperimentId, exportType);
      setNotice(`${exportType.toUpperCase()} export generated inline from measured/pending data.`);
    } catch (exportError) {
      setError(exportError.message);
    } finally {
      setAction(null);
    }
  }

  if (loading) {
    return <Shell>Loading evaluation...</Shell>;
  }

  return (
    <Shell>
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">Medical Memory Platform</p>
            <h1 className="mt-2 text-2xl font-semibold text-slate-950">Evaluation Dashboard</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Research evaluation workspace for seven memory systems. Scores appear only after completed experiment runs.
            </p>
          </div>
          <select
            value={selectedExperimentId}
            onChange={(event) => setSelectedExperimentId(event.target.value)}
            className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-800"
          >
            <option value="">No experiment selected</option>
            {experiments.map((experiment) => (
              <option key={experiment.id} value={experiment.id}>
                {experiment.name} - {experiment.status}
              </option>
            ))}
          </select>
        </div>
      </section>

      {error ? <Notice tone="error" message={error} /> : null}
      {notice ? <Notice tone="success" message={notice} /> : null}
      {action ? <ActionLine action={action} /> : null}

      <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricSummaryCard label="Datasets" value={datasets.length} />
        <MetricSummaryCard label="Metrics" value={metrics.length} />
        <MetricSummaryCard label="Experiments" value={experiments.length} />
        <MetricSummaryCard label="Selected status" value={selectedExperiment?.status ?? "None"} />
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="space-y-6">
          <DatasetSelector datasets={datasets} selectedDatasetId={selectedDatasetId} onChange={setSelectedDatasetId} />
          <ExperimentConfigurator disabled={!selectedDatasetId || action === "create"} onCreate={createExperiment} />
          <ExperimentProgress progress={progress} disabled={!selectedExperimentId || action === "start"} onStart={startExperiment} />
          <SystemSelector />
          <ExportControls disabled={!selectedExperimentId || Boolean(action)} onExport={exportResults} />
        </aside>

        <div className="space-y-6">
          <MetricSelector metrics={metrics} />
          <SystemComparisonTable results={results?.metric_results ?? []} />
          <MetricRankingTable rankings={results?.rankings ?? {}} />
          <StatisticalResults statistics={results?.statistics ?? []} />
          <div className="grid gap-6 xl:grid-cols-2">
            <HallucinationViewer hallucinations={audits.hallucinations} />
            <CitationAuditViewer citations={audits.citations} />
            <ClaimAuditViewer claims={audits.claims} />
            <RetrievalTraceViewer />
            <TemporalTimelineViewer />
            <CorrectionRecoveryViewer />
            <ContradictionViewer />
            <CsmStateTraceViewer />
            <HumanReviewQueue />
          </div>
        </div>
      </section>
    </Shell>
  );
}

function Shell({ children }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8">
          <button
            type="button"
            onClick={() => window.location.assign("/research")}
            className="flex items-center gap-3 rounded-lg focus:outline-none focus:ring-4 focus:ring-blue-100"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-700 text-white">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="hidden text-left sm:block">
              <p className="text-sm font-semibold text-slate-950">Sustha</p>
              <p className="text-xs text-slate-500">Evaluation</p>
            </div>
          </button>
          <button
            type="button"
            onClick={() => window.location.assign("/research")}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Research
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8">{children}</main>
    </div>
  );
}

function Notice({ tone, message }) {
  const style = tone === "success" ? "border-green-200 bg-green-50 text-green-700" : "border-red-200 bg-red-50 text-red-700";
  return <div className={`mt-6 rounded-lg border px-4 py-3 text-sm ${style}`}>{message}</div>;
}

function ActionLine({ action }) {
  return (
    <div className="mt-6 flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
      <Loader2 className="h-4 w-4 animate-spin" />
      {action}
    </div>
  );
}
