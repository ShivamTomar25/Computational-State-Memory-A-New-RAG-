import {
  MetricCard,
  PageHero,
  PlatformShell,
  StatusBadge,
  TableShell,
} from "../platform_shared/PlatformShell";
import { healthServices } from "../platform_shared/platformService";

export function SystemHealthPage() {
  const publicRoute = window.location.pathname === "/status";
  const visibleServices = publicRoute
    ? healthServices.filter((service) => ["API health", "LLM providers", "Export service"].includes(service.name))
    : healthServices;

  return (
    <PlatformShell sectionLabel={publicRoute ? "Status" : "System health"}>
      <PageHero
        eyebrow={publicRoute ? "Public-safe service status" : "Internal authenticated status"}
        title={publicRoute ? "System Status" : "Application Health and System Status"}
        description={publicRoute ? "High-level service availability without internal details." : "Monitor API, databases, queues, indexing, providers, notifications, exports, and recent incidents."}
      />

      <section className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Operational" value={visibleServices.filter((service) => service.status === "Operational").length} />
        <MetricCard label="Degraded" value={visibleServices.filter((service) => service.status === "Degraded").length} />
        <MetricCard label="Partial outage" value={visibleServices.filter((service) => service.status === "Partial Outage").length} />
        <MetricCard label="Last checked" value="11:30 AM" detail="17 July 2026" />
      </section>

      <section className="mt-6">
        <TableShell caption="Service health" columns={publicRoute ? ["Service", "Status"] : ["Service", "Status", "Last Checked", "Latency", "Affected Systems"]}>
          {visibleServices.map((service) => (
            <tr key={service.name}>
              <td className="px-5 py-4 text-sm font-semibold text-slate-950">{service.name}</td>
              <td className="px-5 py-4"><StatusBadge label={service.status} /></td>
              {!publicRoute ? (
                <>
                  <td className="px-5 py-4 text-sm text-slate-600">{service.lastChecked}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{service.latency}</td>
                  <td className="px-5 py-4 text-sm text-slate-600">{service.affected}</td>
                </>
              ) : null}
            </tr>
          ))}
        </TableShell>
      </section>

      {!publicRoute ? (
        <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-base font-semibold text-slate-950">Recent incidents</h2>
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-800">
            Graph service is partially unavailable for GraphRAG indexing jobs.
            No credentials, hostnames, internal IP addresses, or stack traces
            are shown in this UI.
          </div>
        </section>
      ) : null}
    </PlatformShell>
  );
}
