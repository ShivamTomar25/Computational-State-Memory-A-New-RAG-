import { useState } from "react";
import { Activity, AlertCircle, BriefcaseMedical, UsersRound } from "lucide-react";
import {
  MetricCard,
  PageHero,
  PlatformShell,
  SecondaryButton,
  StatusBadge,
  TableShell,
  go,
} from "../platform_shared/PlatformShell";
import {
  adminPatients,
  doctors,
  featureFlags,
  jobs,
  memorySystems,
} from "../platform_shared/platformService";

const adminTabs = ["Overview", "Doctors", "Organizations", "Roles", "Patients", "Memory Systems", "Jobs", "Audit Logs", "Feature Flags", "System Health"];

export function AdminPortalPage() {
  const [activeTab, setActiveTab] = useState("Overview");

  return (
    <PlatformShell sectionLabel="Administration">
      <PageHero
        eyebrow="Administration"
        title="Administration Portal"
        description="Manage operational oversight, doctors, organizations, roles, patients, jobs, audit logs, feature flags, and system health."
      />

      <nav className="mt-6 overflow-x-auto border-b border-slate-200">
        <div className="flex min-w-max gap-1">
          {adminTabs.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => {
                if (tab === "Organizations") {
                  go("/admin/organizations");
                  return;
                }
                if (tab === "Roles") {
                  go("/admin/roles");
                  return;
                }
                if (tab === "Jobs") {
                  go("/admin/jobs");
                  return;
                }
                if (tab === "Audit Logs") {
                  go("/admin/audit");
                  return;
                }
                if (tab === "System Health") {
                  go("/admin/system-health");
                  return;
                }
                setActiveTab(tab);
              }}
              className={`h-11 whitespace-nowrap border-b-2 px-4 text-sm font-medium ${
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

      <section className="mt-6">
        {activeTab === "Overview" ? <AdminOverview /> : null}
        {activeTab === "Doctors" ? <DoctorsTable /> : null}
        {activeTab === "Patients" ? <PatientsTable /> : null}
        {activeTab === "Memory Systems" ? <MemoryTable /> : null}
        {activeTab === "Feature Flags" ? <FeatureFlagsTable /> : null}
      </section>
    </PlatformShell>
  );
}

function AdminOverview() {
  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Active doctors" value={doctors.length} icon={<UsersRound className="h-5 w-5" aria-hidden="true" />} />
        <MetricCard label="Active patients" value={adminPatients.length} icon={<BriefcaseMedical className="h-5 w-5" aria-hidden="true" />} />
        <MetricCard label="Documents processing" value="0" icon={<Activity className="h-5 w-5" aria-hidden="true" />} />
        <MetricCard label="Failed jobs" value={jobs.filter((job) => job.status === "Failed").length} icon={<AlertCircle className="h-5 w-5" aria-hidden="true" />} />
        <MetricCard label="Memory health" value="No data" />
        <MetricCard label="Pending reviews" value="0" />
        <MetricCard label="Security alerts" value="0" />
        <MetricCard label="Recent admin actions" value="0" />
      </section>
      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-950">Recent administrative actions</h2>
        <div className="mt-4 grid gap-3">
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
            No administrative actions yet.
          </div>
        </div>
      </section>
    </div>
  );
}

function DoctorsTable() {
  return (
    <TableShell caption="Doctors" columns={["Doctor ID", "Name", "Email", "Specialization", "Organization", "Status", "Last Login", "Failed Logins", "Created", "Actions"]}>
      {doctors.map((doctor) => (
        <tr key={doctor.id}>
          <td className="px-5 py-4 text-sm text-slate-600">{doctor.id}</td>
          <td className="px-5 py-4 text-sm font-semibold text-slate-950">{doctor.name}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{doctor.email}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{doctor.specialization}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{doctor.organization}</td>
          <td className="px-5 py-4"><StatusBadge label={doctor.status} /></td>
          <td className="px-5 py-4 text-sm text-slate-600">{doctor.lastLogin}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{doctor.failedLogins}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{doctor.createdDate}</td>
          <td className="px-5 py-4">
            <div className="flex flex-wrap gap-2">
              <SecondaryButton>View</SecondaryButton>
              <SecondaryButton>Activate</SecondaryButton>
              <SecondaryButton>Suspend</SecondaryButton>
              <SecondaryButton>Assign Role</SecondaryButton>
            </div>
          </td>
        </tr>
      ))}
    </TableShell>
  );
}

function PatientsTable() {
  return (
    <TableShell caption="Admin patient list" columns={["Patient ID", "Display Name", "Organization", "Assigned Doctor", "Memory Status", "Documents", "Created"]}>
      {adminPatients.map((patient) => (
        <tr key={patient.id}>
          <td className="px-5 py-4 text-sm text-slate-600">{patient.id}</td>
          <td className="px-5 py-4 text-sm font-semibold text-slate-950">{patient.name}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{patient.organization}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{patient.doctor}</td>
          <td className="px-5 py-4"><StatusBadge label={patient.memoryStatus} /></td>
          <td className="px-5 py-4 text-sm text-slate-600">{patient.documents}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{patient.createdDate}</td>
        </tr>
      ))}
    </TableShell>
  );
}

function MemoryTable() {
  return (
    <TableShell caption="Admin memory systems" columns={["System", "Health", "Sync", "Active Jobs", "Last Update", "Actions"]}>
      {memorySystems.map((system) => (
        <tr key={system.id}>
          <td className="px-5 py-4 text-sm font-semibold text-slate-950">{system.name}</td>
          <td className="px-5 py-4"><StatusBadge label={system.health} /></td>
          <td className="px-5 py-4 text-sm text-slate-600">{system.syncStatus}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{system.activeJobs}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{system.lastSuccessfulUpdate}</td>
          <td className="px-5 py-4"><SecondaryButton onClick={() => go("/memory-systems")}>Open</SecondaryButton></td>
        </tr>
      ))}
    </TableShell>
  );
}

function FeatureFlagsTable() {
  return (
    <TableShell caption="Feature flags" columns={["Feature", "Description", "Environment", "Status", "Target", "Last Changed", "Changed By"]}>
      {featureFlags.map((flag) => (
        <tr key={flag.name}>
          <td className="px-5 py-4 text-sm font-semibold text-slate-950">{flag.name}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{flag.description}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{flag.environment}</td>
          <td className="px-5 py-4"><StatusBadge label={flag.enabled} /></td>
          <td className="px-5 py-4 text-sm text-slate-600">{flag.target}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{flag.changed}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{flag.changedBy}</td>
        </tr>
      ))}
    </TableShell>
  );
}
