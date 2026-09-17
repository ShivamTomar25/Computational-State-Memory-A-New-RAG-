import { useState } from "react";
import {
  BarChart3,
  Download,
  Filter,
} from "lucide-react";
import {
  EmptyState,
  MetricCard,
  PageHero,
  PlatformShell,
  SecondaryButton,
  SelectField,
  StatePanel,
  StatusBadge,
  TableShell,
} from "../platform_shared/PlatformShell";
import {
  architectureMetrics,
  feedbackIssues,
  researchSummary,
} from "../platform_shared/platformService";

const demoOptions = ["Ready", "Loading", "Empty", "Error", "Unauthorized"];

export function ResearchDashboardPage() {
  const [dateRange, setDateRange] = useState("Last 30 Days");
  const [architecture, setArchitecture] = useState("All");
  const [cohort, setCohort] = useState("All Cohorts");
  const [experiment, setExperiment] = useState("All Experiments");
  const [demoState, setDemoState] = useState("Ready");

  return (
    <PlatformShell sectionLabel="Research dashboard">
      <PageHero
        eyebrow="Research and evaluation"
        title="Research Dashboard"
        description="Review architecture performance, evidence quality, clinician feedback, and experiment outcomes."
        actions={
          <>
            <SecondaryButton>
              <Download className="h-4 w-4" aria-hidden="true" />
              Export JSON
            </SecondaryButton>
            <SecondaryButton>
              <Download className="h-4 w-4" aria-hidden="true" />
              Export CSV
            </SecondaryButton>
            <SecondaryButton onClick={() => window.location.assign("/evaluation")}>
              <BarChart3 className="h-4 w-4" aria-hidden="true" />
              Evaluation Dashboard
            </SecondaryButton>
          </>
        }
      >
        <p className="mt-3 text-sm font-medium text-slate-600">
          Metrics are descriptive. This page does not automatically claim that
          one architecture is superior.
        </p>
      </PageHero>

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          <SelectField label="Date range" value={dateRange} onChange={setDateRange} options={["Last 7 Days", "Last 30 Days", "Last 90 Days", "Custom Range"]} />
          <SelectField label="Architecture" value={architecture} onChange={setArchitecture} options={["All", "Dense RAG", "Hybrid RAG", "GraphRAG", "CSM"]} />
          <SelectField label="Patient cohort" value={cohort} onChange={setCohort} options={["All Cohorts", "Diabetes follow-up cohort", "Synthetic cardiometabolic cohort"]} />
          <SelectField label="Experiment" value={experiment} onChange={setExperiment} options={["All Experiments", "Medication conflict comparison", "Citation quality baseline"]} />
          <SelectField label="Demo state" value={demoState} onChange={setDemoState} options={demoOptions} />
        </div>
      </section>

      {demoState === "Unauthorized" ? (
        <div className="mt-6">
          <StatePanel title="Access denied" text="This account is not authorized to view research metrics." />
        </div>
      ) : null}

      {demoState === "Error" ? (
        <div className="mt-6">
          <StatePanel title="Research metrics unavailable" text="The dashboard could not load summary metrics. Retry after checking service status." />
        </div>
      ) : null}

      {demoState === "Empty" ? (
        <div className="mt-6">
          <EmptyState title="No research metrics available" text="No evaluated questions or experiment outcomes match the selected filters." />
        </div>
      ) : null}

      {demoState === "Loading" ? <ResearchSkeleton /> : null}

      {demoState === "Ready" ? (
        <>
          <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {researchSummary.slice(0, 8).map(([label, value]) => (
              <MetricCard key={label} label={label} value={value} icon={<BarChart3 className="h-5 w-5" aria-hidden="true" />} />
            ))}
          </section>

          <section className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="space-y-6">
              <MetricSection title="Architecture performance">
                <ArchitectureTable />
              </MetricSection>
              <MetricSection title="Evaluation quality">
                <QualityGrid />
              </MetricSection>
              <MetricSection title="Evidence metrics">
                <EvidenceMetrics />
              </MetricSection>
            </div>

            <aside className="space-y-6">
              <MetricSection title="Feedback analysis">
                <div className="space-y-3">
                  {feedbackIssues.map((issue) => (
                    <BarRow key={issue.issue} label={issue.issue} value={issue.count} max={20} />
                  ))}
                </div>
              </MetricSection>
              <MetricSection title="Chart summaries">
                <div className="space-y-4">
                  <ChartCard title="Latency distribution" value="Available by architecture" />
                  <ChartCard title="Token usage" value="Mean and p95 shown in table" />
                  <ChartCard title="Cost over time" value="Backend report pending" unavailable />
                  <ChartCard title="Evaluation completion" value="74% completed" />
                </div>
              </MetricSection>
            </aside>
          </section>
        </>
      ) : null}
    </PlatformShell>
  );
}

function ArchitectureTable() {
  return (
    <TableShell
      caption="Architecture comparison"
      columns={["Architecture", "Runs", "Completion Rate", "Mean Latency", "Mean Tokens", "Estimated Cost", "Citation Coverage", "Mean Human Rating", "Failure Rate"]}
    >
      {architectureMetrics.map((row) => (
        <tr key={row.architecture}>
          <td className="px-5 py-4 text-sm font-semibold text-slate-950">{row.architecture}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{row.runs}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{row.completion}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{row.latency}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{row.tokens}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{row.cost}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{row.coverage}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{row.rating}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{row.failure}</td>
        </tr>
      ))}
    </TableShell>
  );
}

function QualityGrid() {
  const rows = [
    ["Correctness ratings", "Available"],
    ["Completeness ratings", "Available"],
    ["Citation-quality ratings", "Available"],
    ["Clinical-usefulness ratings", "Available"],
    ["Clarity ratings", "Available"],
    ["Uncertainty handling", "Not yet computed"],
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {rows.map(([label, value]) => (
        <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-semibold text-slate-950">{label}</p>
          <div className="mt-2">
            <StatusBadge label={value === "Available" ? "Ready" : "Draft"} />
          </div>
          <p className="mt-2 text-sm text-slate-600">{value}</p>
        </div>
      ))}
    </div>
  );
}

function EvidenceMetrics() {
  const rows = [
    ["Citation precision", "Not yet computed"],
    ["Citation recall", "Not yet computed"],
    ["Context precision", "82%"],
    ["Context recall", "78%"],
    ["Unsupported-claim rate", "6%"],
    ["Missing-citation rate", "9%"],
    ["Conflict-detection rate", "18%"],
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {rows.map(([label, value]) => (
        <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm text-slate-500">{label}</p>
          <p className="mt-2 text-lg font-semibold text-slate-950">{value}</p>
        </div>
      ))}
    </div>
  );
}

function MetricSection({ title, children }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-4 flex items-center gap-2">
        <Filter className="h-4 w-4 text-blue-700" aria-hidden="true" />
        <h2 className="text-base font-semibold text-slate-950">{title}</h2>
      </div>
      {children}
    </section>
  );
}

function BarRow({ label, value, max }) {
  return (
    <div>
      <div className="flex items-center justify-between gap-4 text-sm">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="text-slate-500">{value}</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-blue-700" style={{ width: `${Math.min((value / max) * 100, 100)}%` }} />
      </div>
    </div>
  );
}

function ChartCard({ title, value, unavailable }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-950">{title}</p>
      <p className="mt-2 text-sm text-slate-600">{value}</p>
      {unavailable ? <p className="mt-2 text-xs font-medium text-amber-700">Not yet computed</p> : null}
    </div>
  );
}

function ResearchSkeleton() {
  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {[1, 2, 3, 4].map((item) => (
        <div key={item} className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="h-4 w-28 rounded bg-slate-200" />
          <div className="mt-4 h-6 w-20 rounded bg-slate-100" />
        </div>
      ))}
    </div>
  );
}
