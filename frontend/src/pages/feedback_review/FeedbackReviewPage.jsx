import { useState } from "react";
import {
  Drawer,
  InfoRow,
  PageHero,
  PlatformShell,
  SecondaryButton,
  SelectField,
  StatusBadge,
  TableShell,
  go,
  inputClass,
} from "../platform_shared/PlatformShell";
import { feedbackReports } from "../platform_shared/platformService";

export function FeedbackReviewPage() {
  const [reports, setReports] = useState(feedbackReports);
  const [selectedReport, setSelectedReport] = useState(null);
  const [statusFilter, setStatusFilter] = useState("All");

  const visibleReports = reports.filter(
    (report) => statusFilter === "All" || report.status === statusFilter,
  );

  function updateReport(id, patch) {
    setReports((current) =>
      current.map((report) => (report.id === id ? { ...report, ...patch } : report)),
    );
    setSelectedReport((current) =>
      current?.id === id ? { ...current, ...patch } : current,
    );
  }

  return (
    <PlatformShell sectionLabel="Feedback review">
      <PageHero
        eyebrow="Research feedback"
        title="Feedback and Issue Review"
        description="Inspect issues reported on AI answers without allowing reviewer notes to modify patient evidence."
      />

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <SelectField label="Review status" value={statusFilter} onChange={setStatusFilter} options={["All", "New", "In Review", "Confirmed", "Not Reproducible", "Resolved", "Deferred"]} />
      </section>

      <section className="mt-6">
        <TableShell caption="Feedback reports" columns={["Report Date", "Patient", "Conversation", "Question", "Architecture", "Issue Category", "Severity", "Review Status", "Reporter", "Reviewer", "Actions"]}>
          {visibleReports.map((report) => (
            <tr key={report.id}>
              <td className="px-5 py-4 text-sm text-slate-600">{report.reportDate}</td>
              <td className="px-5 py-4 text-sm text-slate-600">{report.patient}</td>
              <td className="px-5 py-4 text-sm text-slate-600">{report.conversation}</td>
              <td className="px-5 py-4 text-sm text-slate-600">{report.question}</td>
              <td className="px-5 py-4 text-sm text-slate-600">{report.architecture}</td>
              <td className="px-5 py-4 text-sm text-slate-600">{report.issue}</td>
              <td className="px-5 py-4"><StatusBadge label={report.severity} /></td>
              <td className="px-5 py-4"><StatusBadge label={report.status} /></td>
              <td className="px-5 py-4 text-sm text-slate-600">{report.reporter}</td>
              <td className="px-5 py-4 text-sm text-slate-600">{report.reviewer}</td>
              <td className="px-5 py-4"><SecondaryButton onClick={() => setSelectedReport(report)}>Review</SecondaryButton></td>
            </tr>
          ))}
        </TableShell>
      </section>

      {selectedReport ? (
        <Drawer title={selectedReport.issue} subtitle="Issue detail" onClose={() => setSelectedReport(null)}>
          <div className="space-y-5">
            <dl className="grid gap-3 text-sm">
              <InfoRow label="Question" value={selectedReport.question} />
              <InfoRow label="Answer" value="Synthetic answer text is summarized here for review." />
              <InfoRow label="Architecture" value={selectedReport.architecture} />
              <InfoRow label="Memory version" value="12" />
              <InfoRow label="Citations" value="ev-med-stop, ev-prescription-active" />
              <InfoRow label="Execution metadata" value="Trace and latency metadata available" />
              <InfoRow label="Reporter comment" value={selectedReport.comment} />
              <InfoRow label="Related evidence" value="Medication conflict evidence" />
              <InfoRow label="Related trace" value={`trace-feedback-${selectedReport.id}`} />
            </dl>
            <div className="grid gap-4">
              <SelectField label="Assigned reviewer" value={selectedReport.reviewer} onChange={(value) => updateReport(selectedReport.id, { reviewer: value })} options={["Unassigned", "Research Admin", "Clinical Reviewer"]} />
              <SelectField label="Review status" value={selectedReport.status} onChange={(value) => updateReport(selectedReport.id, { status: value })} options={["New", "In Review", "Confirmed", "Not Reproducible", "Resolved", "Deferred"]} />
              <label className="block">
                <span className="mb-2 block text-sm font-medium text-slate-700">Reviewer notes</span>
                <textarea
                  rows={4}
                  className={`${inputClass()} h-auto py-3`}
                  placeholder="Add review note. This does not modify patient evidence."
                />
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              <SecondaryButton onClick={() => go("/patients/1/chat/conv-1")}>Open Conversation</SecondaryButton>
              <SecondaryButton onClick={() => go("/patients/1/evidence")}>Open Evidence</SecondaryButton>
              <SecondaryButton onClick={() => go("/research/experiments/exp-1")}>Link Experiment</SecondaryButton>
            </div>
          </div>
        </Drawer>
      ) : null}
    </PlatformShell>
  );
}
