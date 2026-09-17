import { useState } from "react";
import { Download, Plus, XCircle } from "lucide-react";
import {
  PageHero,
  PlatformShell,
  PrimaryButton,
  SecondaryButton,
  SelectField,
  StatusBadge,
  TableShell,
  TextField,
} from "../platform_shared/PlatformShell";
import { exportHistory } from "../platform_shared/platformService";

export function ExportCenterPage() {
  const [exports, setExports] = useState(exportHistory);
  const [form, setForm] = useState({
    type: "Patient Evidence",
    target: "",
    dateRange: "Last 30 Days",
    sections: "",
    format: "JSON",
    deidentify: "No",
    reason: "",
  });
  const [error, setError] = useState("");

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setError("");
  }

  function requestExport(event) {
    event.preventDefault();
    if (!form.reason.trim()) {
      setError("Reason for export is required.");
      return;
    }

    setExports((current) => [
      {
        id: `exp-out-${Date.now()}`,
        type: form.type,
        requestedBy: "Current doctor",
        requestedDate: "Just now",
        status: "Preparing",
        size: "Pending",
        expiry: "Pending",
      },
      ...current,
    ]);
    setForm((current) => ({ ...current, reason: "" }));
  }

  function cancelExport(id) {
    setExports((current) =>
      current.map((item) =>
        item.id === id ? { ...item, status: "Cancelled" } : item,
      ),
    );
  }

  return (
    <PlatformShell sectionLabel="Exports">
      <PageHero
        eyebrow="Data export"
        title="Data Export Center"
        description="Request and track exports using backend-authorized scopes and short-lived signed download links."
      />

      <section className="mt-6 grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <form onSubmit={requestExport} className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-base font-semibold text-slate-950">Request export</h2>
          <div className="mt-5 grid gap-5">
            <SelectField label="Export type" value={form.type} onChange={(value) => update("type", value)} options={["Patient Summary", "Patient Documents Metadata", "Patient Evidence", "Conversation", "Comparison", "Experiment Results", "Research Metrics", "Audit Logs"]} />
            <TextField label="Patient or experiment" value={form.target} onChange={(value) => update("target", value)} />
            <SelectField label="Date range" value={form.dateRange} onChange={(value) => update("dateRange", value)} options={["All Time", "Last 7 Days", "Last 30 Days", "Custom Range"]} />
            <TextField label="Included sections" value={form.sections} onChange={(value) => update("sections", value)} />
            <SelectField label="File format" value={form.format} onChange={(value) => update("format", value)} options={["JSON", "CSV", "PDF", "ZIP"]} />
            <SelectField label="De-identification" value={form.deidentify} onChange={(value) => update("deidentify", value)} options={["No", "Yes, if backend supports it"]} />
            <TextField label="Reason for export" value={form.reason} onChange={(value) => update("reason", value)} placeholder="Clinical review, research export, or compliance request" />
          </div>
          {error ? <p className="mt-4 text-sm font-medium text-red-700">{error}</p> : null}
          <div className="mt-5">
            <PrimaryButton type="submit">
              <Plus className="h-4 w-4" aria-hidden="true" />
              Request Export
            </PrimaryButton>
          </div>
        </form>

        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-base font-semibold text-slate-950">Export history</h2>
          <div className="mt-4">
            <TableShell caption="Export history" columns={["Export ID", "Type", "Requested By", "Requested Date", "Status", "Size", "Expiry", "Actions"]}>
              {exports.map((item) => (
                <tr key={item.id}>
                  <td className="px-5 py-4 text-sm text-slate-600">{item.id}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{item.type}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{item.requestedBy}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{item.requestedDate}</td>
                  <td className="px-5 py-4"><StatusBadge label={item.status} /></td>
                  <td className="px-5 py-4 text-sm text-slate-600">{item.size}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{item.expiry}</td>
                  <td className="px-5 py-4">
                    <div className="flex flex-wrap gap-2">
                      <SecondaryButton disabled={item.status !== "Ready"}>
                        <Download className="h-4 w-4" aria-hidden="true" />
                        Download
                      </SecondaryButton>
                      <SecondaryButton disabled={item.status !== "Preparing"} onClick={() => cancelExport(item.id)}>
                        <XCircle className="h-4 w-4" aria-hidden="true" />
                        Cancel
                      </SecondaryButton>
                    </div>
                  </td>
                </tr>
              ))}
            </TableShell>
          </div>
        </section>
      </section>
    </PlatformShell>
  );
}
