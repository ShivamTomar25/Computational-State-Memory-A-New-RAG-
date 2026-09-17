import { useMemo, useState } from "react";
import { Download, Search } from "lucide-react";
import {
  Drawer,
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
  inputClass,
} from "../platform_shared/PlatformShell";
import { auditEvents } from "../platform_shared/platformService";

export function AuditLogPage() {
  const [query, setQuery] = useState("");
  const [action, setAction] = useState("All");
  const [result, setResult] = useState("All");
  const [demoState, setDemoState] = useState("Ready");
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [exportReason, setExportReason] = useState("");

  const visibleEvents = useMemo(() => {
    const source = demoState === "Empty" ? [] : auditEvents;
    const search = query.trim().toLowerCase();

    return source.filter((event) => {
      const text = Object.values(event).join(" ").toLowerCase();
      return (
        (!search || text.includes(search)) &&
        (action === "All" || event.action === action) &&
        (result === "All" || event.result === result)
      );
    });
  }, [query, action, result, demoState]);

  return (
    <PlatformShell sectionLabel="Audit logs">
      <PageHero
        eyebrow="Compliance"
        title="Audit Log Viewer"
        description="Review authorized audit events without exposing secrets, raw medical text, passwords, tokens, or stack traces."
        actions={
          <SecondaryButton onClick={() => setExportOpen(true)}>
            <Download className="h-4 w-4" aria-hidden="true" />
            Export Audit Logs
          </SecondaryButton>
        }
      />

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_180px_180px_180px]">
          <label className="relative block">
            <span className="mb-2 block text-sm font-medium text-slate-700">Search</span>
            <Search className="pointer-events-none absolute left-3 top-[42px] h-4 w-4 text-slate-400" aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search actor, patient, action, trace ID..."
              className={inputClass("pl-9")}
            />
          </label>
          <SelectField label="Action" value={action} onChange={setAction} options={["All", "answer generated", "document uploaded", "role changed"]} />
          <SelectField label="Result" value={result} onChange={setResult} options={["All", "Success", "Failed"]} />
          <SelectField label="Demo state" value={demoState} onChange={setDemoState} options={["Ready", "Loading", "Empty", "Error", "Unauthorized"]} />
        </div>
      </section>

      {demoState === "Unauthorized" ? (
        <div className="mt-6">
          <StatePanel title="Access denied" text="This route is available only to authorized administrators and compliance reviewers." />
        </div>
      ) : null}
      {demoState === "Error" ? (
        <div className="mt-6">
          <StatePanel title="Audit request failed" text="Audit logs could not be loaded. Raw backend details are not displayed." />
        </div>
      ) : null}
      {demoState === "Loading" ? <AuditSkeleton /> : null}

      {demoState === "Ready" ? (
        <section className="mt-6">
          <TableShell caption="Audit events" columns={["Timestamp", "Actor", "Role", "Organization", "Patient", "Action", "Resource", "Result", "Reason", "Trace ID", "Actions"]}>
            {visibleEvents.map((event) => (
              <tr key={event.id} className="hover:bg-slate-50">
                <td className="px-5 py-4 text-sm text-slate-600">{event.timestamp}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{event.actor}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{event.role}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{event.organization}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{event.patient || "Not patient-scoped"}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{event.action}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{event.resource}</td>
                <td className="px-5 py-4"><StatusBadge label={event.result} /></td>
                <td className="px-5 py-4 text-sm text-slate-600">{event.reason}</td>
                <td className="px-5 py-4 text-sm text-slate-600">{event.traceId}</td>
                <td className="px-5 py-4">
                  <SecondaryButton onClick={() => setSelectedEvent(event)}>View</SecondaryButton>
                </td>
              </tr>
            ))}
          </TableShell>
          {!visibleEvents.length ? (
            <div className="mt-6">
              <StatePanel title="No audit events found" text="No events match the selected filters." />
            </div>
          ) : null}
        </section>
      ) : null}

      {selectedEvent ? (
        <Drawer title={selectedEvent.action} subtitle="Audit event detail" onClose={() => setSelectedEvent(null)}>
          <dl className="grid gap-3 text-sm">
            <InfoRow label="Actor" value={selectedEvent.actor} />
            <InfoRow label="Authorization context" value={`${selectedEvent.role} at ${selectedEvent.organization}`} />
            <InfoRow label="Before summary" value="Safe summary only" />
            <InfoRow label="After summary" value="Safe summary only" />
            <InfoRow label="Reason" value={selectedEvent.reason} />
            <InfoRow label="Request identifier" value={`req-${selectedEvent.id}`} />
            <InfoRow label="Trace identifier" value={selectedEvent.traceId} />
          </dl>
        </Drawer>
      ) : null}

      {exportOpen ? (
        <Modal title="Export Audit Logs" onClose={() => setExportOpen(false)}>
          <TextField label="Reason for export" value={exportReason} onChange={setExportReason} placeholder="Compliance review" />
          <div className="mt-5 flex justify-end gap-3">
            <SecondaryButton onClick={() => setExportOpen(false)}>Cancel</SecondaryButton>
            <PrimaryButton disabled={!exportReason.trim()} onClick={() => setExportOpen(false)}>Request Export</PrimaryButton>
          </div>
        </Modal>
      ) : null}
    </PlatformShell>
  );
}

function AuditSkeleton() {
  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
      <div className="h-4 w-40 rounded bg-slate-200" />
      <div className="mt-4 h-5 w-2/3 rounded bg-slate-200" />
    </div>
  );
}
