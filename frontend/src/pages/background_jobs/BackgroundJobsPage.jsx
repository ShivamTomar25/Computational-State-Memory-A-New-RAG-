import { useMemo, useState } from "react";
import { RefreshCcw, XCircle } from "lucide-react";
import {
  Drawer,
  InfoRow,
  MetricCard,
  PageHero,
  PlatformShell,
  SecondaryButton,
  SelectField,
  StatePanel,
  StatusBadge,
  TableShell,
} from "../platform_shared/PlatformShell";
import { jobs as jobFixtures } from "../platform_shared/platformService";

const statusOptions = ["All", "Queued", "Running", "Complete", "Failed", "Retrying", "Cancelled", "Dead Letter"];

export function BackgroundJobsPage() {
  const [jobs, setJobs] = useState(jobFixtures);
  const [statusFilter, setStatusFilter] = useState("All");
  const [demoState, setDemoState] = useState("Ready");
  const [selectedJob, setSelectedJob] = useState(null);

  const visibleJobs = useMemo(() => {
    const source = demoState === "Empty" ? [] : jobs;
    return source.filter((job) => statusFilter === "All" || job.status === statusFilter);
  }, [jobs, statusFilter, demoState]);

  function updateJob(id, status) {
    setJobs((current) =>
      current.map((job) => (job.id === id ? { ...job, status } : job)),
    );
  }

  return (
    <PlatformShell sectionLabel="Background jobs">
      <PageHero
        eyebrow="Administration"
        title="Background Jobs and Queue Monitor"
        description="Monitor upload, extraction, indexing, notification, export, retry, and dead-letter queues without exposing sensitive payloads."
      />

      <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
        <MetricCard label="Queued" value={jobs.filter((job) => job.status === "Queued").length} />
        <MetricCard label="Running" value={jobs.filter((job) => job.status === "Running").length} />
        <MetricCard label="Complete today" value={jobs.filter((job) => job.status === "Complete").length} />
        <MetricCard label="Failed" value={jobs.filter((job) => job.status === "Failed").length} />
        <MetricCard label="Retrying" value={jobs.filter((job) => job.status === "Retrying").length} />
        <MetricCard label="Dead letter" value={jobs.filter((job) => job.status === "Dead Letter").length} />
      </section>

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField label="Status" value={statusFilter} onChange={setStatusFilter} options={statusOptions} />
          <SelectField label="Demo state" value={demoState} onChange={setDemoState} options={["Ready", "Loading", "Empty", "Error", "Unauthorized"]} />
        </div>
      </section>

      {demoState === "Unauthorized" ? (
        <div className="mt-6">
          <StatePanel title="Access denied" text="This account is not authorized to inspect background jobs." />
        </div>
      ) : null}
      {demoState === "Error" ? (
        <div className="mt-6">
          <StatePanel title="Jobs request failed" text="Queue data could not be loaded." />
        </div>
      ) : null}
      {demoState === "Loading" ? <JobsSkeleton /> : null}
      {demoState === "Empty" ? (
        <div className="mt-6">
          <StatePanel title="No jobs found" text="No jobs are currently visible for this queue scope." />
        </div>
      ) : null}

      {demoState === "Ready" ? (
        <section className="mt-6">
          <TableShell caption="Background jobs" columns={["Job ID", "Type", "Patient", "Document", "Memory System", "Status", "Progress", "Attempts", "Started", "Duration", "Last Error", "Actions"]}>
            {visibleJobs.map((job) => (
              <tr key={job.id}>
                <td className="px-5 py-4 text-sm text-slate-600">{job.id}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{job.type}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{job.patient || "Not patient-scoped"}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{job.document || "Not applicable"}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{job.memorySystem || "Not applicable"}</td>
                <td className="px-5 py-4"><StatusBadge label={job.status} /></td>
                <td className="px-5 py-4 text-sm text-slate-600">{job.progress}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{job.attempts}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{job.started}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{job.duration}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{job.lastError}</td>
                <td className="px-5 py-4">
                  <div className="flex flex-wrap gap-2">
                    <SecondaryButton onClick={() => setSelectedJob(job)}>Details</SecondaryButton>
                    <SecondaryButton onClick={() => updateJob(job.id, "Retrying")}>
                      <RefreshCcw className="h-4 w-4" aria-hidden="true" />
                      Retry
                    </SecondaryButton>
                    <SecondaryButton onClick={() => updateJob(job.id, "Cancelled")}>
                      <XCircle className="h-4 w-4" aria-hidden="true" />
                      Cancel
                    </SecondaryButton>
                  </div>
                </td>
              </tr>
            ))}
          </TableShell>
          {!visibleJobs.length ? (
            <div className="mt-6">
              <StatePanel title="No jobs match the selected filter" text="Choose another status to inspect queue activity." />
            </div>
          ) : null}
        </section>
      ) : null}

      {selectedJob ? (
        <Drawer title={selectedJob.id} subtitle="Job detail" onClose={() => setSelectedJob(null)}>
          <dl className="grid gap-3 text-sm">
            <InfoRow label="Safe metadata" value={`${selectedJob.type} for ${selectedJob.patient || "system resource"}`} />
            <InfoRow label="Processing stages" value="Queued, validated, processed, indexed" />
            <InfoRow label="Attempts" value={selectedJob.attempts} />
            <InfoRow label="Started" value={selectedJob.started} />
            <InfoRow label="Duration" value={selectedJob.duration} />
            <InfoRow label="Error summary" value={selectedJob.lastError} />
            <InfoRow label="Trace ID" value={selectedJob.traceId} />
            <InfoRow label="Related resource" value={selectedJob.document || selectedJob.memorySystem || "Export request"} />
          </dl>
        </Drawer>
      ) : null}
    </PlatformShell>
  );
}

function JobsSkeleton() {
  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
      <div className="h-4 w-32 rounded bg-slate-200" />
      <div className="mt-3 h-5 w-2/3 rounded bg-slate-100" />
    </div>
  );
}
