import { useState } from "react";
import {
  PageHero,
  PlatformShell,
  SecondaryButton,
  StatusBadge,
  TableShell,
} from "../platform_shared/PlatformShell";
import { organizations, roles } from "../platform_shared/platformService";

const permissionGroups = [
  "Patients",
  "Documents",
  "Evidence",
  "Chat",
  "Compare",
  "CSM",
  "Research",
  "Exports",
  "Audit",
  "Administration",
];

export function OrganizationRolesPage() {
  const defaultTab = window.location.pathname.endsWith("/roles") ? "Roles" : "Organizations";
  const [activeTab, setActiveTab] = useState(defaultTab);

  return (
    <PlatformShell sectionLabel="Organizations and roles">
      <PageHero
        eyebrow="Administration"
        title="Organization and Role Management"
        description="Manage organization metadata and review role permissions. Backend authorization remains the source of truth."
      />

      <nav className="mt-6 overflow-x-auto border-b border-slate-200">
        <div className="flex min-w-max gap-1">
          {["Organizations", "Roles"].map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`h-11 border-b-2 px-4 text-sm font-medium ${
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
        {activeTab === "Organizations" ? <OrganizationsTable /> : <RolesMatrix />}
      </section>
    </PlatformShell>
  );
}

function OrganizationsTable() {
  return (
    <TableShell caption="Organizations" columns={["Organization", "Type", "Status", "Doctors", "Patients", "Created", "Actions"]}>
      {organizations.map((organization) => (
        <tr key={organization.id}>
          <td className="px-5 py-4 text-sm font-semibold text-slate-950">{organization.name}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{organization.type}</td>
          <td className="px-5 py-4"><StatusBadge label={organization.status} /></td>
          <td className="px-5 py-4 text-sm text-slate-600">{organization.doctorCount}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{organization.patientCount}</td>
          <td className="px-5 py-4 text-sm text-slate-600">{organization.createdDate}</td>
          <td className="px-5 py-4">
            <div className="flex flex-wrap gap-2">
              <SecondaryButton>View</SecondaryButton>
              <SecondaryButton>Edit Metadata</SecondaryButton>
              <SecondaryButton>Activate</SecondaryButton>
              <SecondaryButton>Suspend</SecondaryButton>
            </div>
          </td>
        </tr>
      ))}
    </TableShell>
  );
}

function RolesMatrix() {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-950">Permission matrix</h2>
      <p className="mt-2 text-sm text-slate-600">
        Frontend controls are permission-aware, but backend enforcement is required for every protected action.
      </p>
      <div className="mt-5 overflow-x-auto">
        <table className="min-w-full text-left">
          <caption className="sr-only">Role permission matrix</caption>
          <thead className="bg-slate-50">
            <tr>
              <th className="px-5 py-3 text-xs font-semibold uppercase text-slate-500">Role</th>
              {permissionGroups.map((group) => (
                <th key={group} className="px-5 py-3 text-xs font-semibold uppercase text-slate-500">{group}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {roles.map((role) => (
              <tr key={role.name}>
                <td className="px-5 py-4 text-sm font-semibold text-slate-950">{role.name}</td>
                {permissionGroups.map((group) => (
                  <td key={group} className="px-5 py-4 text-sm">
                    <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${
                      role.permissions.includes(group)
                        ? "border-green-200 bg-green-50 text-green-700"
                        : "border-slate-200 bg-slate-50 text-slate-500"
                    }`}>
                      {role.permissions.includes(group) ? "Allowed" : "No access"}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
