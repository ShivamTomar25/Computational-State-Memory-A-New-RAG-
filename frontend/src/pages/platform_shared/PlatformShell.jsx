import {
  ArrowLeft,
  Bell,
  ChevronDown,
  LogOut,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import { clearAuthSession, getStoredDoctor } from "../login_page/authApi";

export const platformPatient = {
  id: "",
  displayName: "Patient",
  systemPatientId: "Patient record",
  age: null,
  sex: "Not recorded",
  primaryCondition: "Not recorded",
  memoryVersion: 0,
  lastUpdated: "Not recorded",
};

const navLinks = [
  { label: "Patients", href: "/patients" },
  { label: "Evidence", href: "/evidence" },
  { label: "Memory", href: "/memory-systems" },
  { label: "Research", href: "/research" },
  { label: "Search", href: "/search" },
  { label: "Admin", href: "/admin" },
];

const statusStyles = {
  Active: "border-green-200 bg-green-50 text-green-700",
  Ready: "border-green-200 bg-green-50 text-green-700",
  Healthy: "border-green-200 bg-green-50 text-green-700",
  Operational: "border-green-200 bg-green-50 text-green-700",
  Complete: "border-green-200 bg-green-50 text-green-700",
  Enabled: "border-green-200 bg-green-50 text-green-700",
  Success: "border-green-200 bg-green-50 text-green-700",
  Running: "border-blue-200 bg-blue-50 text-blue-700",
  Processing: "border-amber-200 bg-amber-50 text-amber-700",
  Degraded: "border-amber-200 bg-amber-50 text-amber-700",
  "Out of Sync": "border-amber-200 bg-amber-50 text-amber-700",
  "Partial Outage": "border-amber-200 bg-amber-50 text-amber-700",
  "Pending Review": "border-blue-200 bg-blue-50 text-blue-700",
  Draft: "border-slate-200 bg-slate-50 text-slate-600",
  Queued: "border-slate-200 bg-slate-50 text-slate-600",
  Archived: "border-slate-200 bg-slate-50 text-slate-600",
  Disabled: "border-slate-200 bg-slate-50 text-slate-600",
  Failed: "border-red-200 bg-red-50 text-red-700",
  Error: "border-red-200 bg-red-50 text-red-700",
  Outage: "border-red-200 bg-red-50 text-red-700",
  High: "border-red-200 bg-red-50 text-red-700",
  Medium: "border-amber-200 bg-amber-50 text-amber-700",
  Low: "border-slate-200 bg-slate-50 text-slate-600",
  New: "border-blue-200 bg-blue-50 text-blue-700",
  "In Review": "border-amber-200 bg-amber-50 text-amber-700",
  Resolved: "border-green-200 bg-green-50 text-green-700",
  Trashed: "border-red-200 bg-red-50 text-red-700",
};

export function PlatformShell({ children, sectionLabel = "Platform", maxWidth = "max-w-7xl" }) {
  const doctor = getStoredDoctor();
  const doctorName = doctor?.full_name ?? "Doctor";

  function logout() {
    clearAuthSession();
    go("/");
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className={`mx-auto flex h-16 ${maxWidth} items-center justify-between px-5 sm:px-8`}>
          <button
            type="button"
            onClick={() => go("/patients")}
            className="flex items-center gap-3 rounded-lg focus:outline-none focus:ring-4 focus:ring-blue-100"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-700 text-white">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="hidden text-left sm:block">
              <p className="text-sm font-semibold text-slate-950">
                Medical Memory Platform
              </p>
              <p className="text-xs text-slate-500">{sectionLabel}</p>
            </div>
          </button>

          <nav className="hidden items-center gap-1 lg:flex" aria-label="Main navigation">
            {navLinks.map((link) => (
              <button
                key={link.href}
                type="button"
                onClick={() => go(link.href)}
                className="h-10 rounded-lg px-3 text-sm font-medium text-slate-600 transition hover:bg-slate-50 hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-blue-100"
              >
                {link.label}
              </button>
            ))}
          </nav>

          <div className="flex items-center gap-2 sm:gap-4">
            <button
              type="button"
              onClick={() => go("/notifications")}
              className="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
              aria-label="Open notifications"
            >
              <Bell className="h-4 w-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={() => go("/settings")}
              className="hidden h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100 sm:flex"
            >
              <UserRound className="h-4 w-4" aria-hidden="true" />
              {doctorName}
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={logout}
              className="flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </div>
      </header>

      <main className={`mx-auto ${maxWidth} px-5 py-8 sm:px-8`}>
        {children}
      </main>
    </div>
  );
}

export function BackButton({ label = "Back", to = "/patients" }) {
  return (
    <button
      type="button"
      onClick={() => go(to)}
      className="mb-5 inline-flex items-center gap-2 rounded text-sm font-medium text-slate-600 transition hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-blue-100"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      {label}
    </button>
  );
}

export function PageHero({ eyebrow, title, description, actions, children }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div>
          {eyebrow ? (
            <p className="text-sm font-medium text-slate-500">{eyebrow}</p>
          ) : null}
          <h1 className="mt-1 text-2xl font-semibold text-slate-950">
            {title}
          </h1>
          {description ? (
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              {description}
            </p>
          ) : null}
          {children}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
    </section>
  );
}

export function PatientBanner({ patient = platformPatient }) {
  const demographics = patient.age
    ? `${patient.age} years, ${patient.sex}`
    : patient.sex || "Not recorded";

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">
            Patient: {patient.displayName} - {patient.systemPatientId}
          </p>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {demographics}. Primary condition: {patient.primaryCondition}
          </p>
        </div>
        <div className="grid gap-2 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 sm:grid-cols-2">
          <p>Patient memory version: {patient.memoryVersion}</p>
          <p>Last updated: {patient.lastUpdated}</p>
        </div>
      </div>
    </section>
  );
}

export function MetricCard({ label, value, detail, icon }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
          {detail ? <p className="mt-1 text-xs text-slate-500">{detail}</p> : null}
        </div>
        {icon ? (
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
            {icon}
          </div>
        ) : null}
      </div>
    </article>
  );
}

export function StatusBadge({ label }) {
  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${statusStyles[label] || "border-slate-200 bg-slate-50 text-slate-600"}`}>
      {label}
    </span>
  );
}

export function InfoRow({ label, value }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{String(value ?? "Not recorded")}</dd>
    </div>
  );
}

export function PrimaryButton({ children, onClick, disabled, type = "button" }) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {children}
    </button>
  );
}

export function SecondaryButton({ children, onClick, disabled, type = "button" }) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {children}
    </button>
  );
}

export function TextField({ label, value, onChange, placeholder, type = "text" }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-slate-700">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className={inputClass()}
      />
    </label>
  );
}

export function SelectField({ label, value, onChange, options }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-slate-700">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={inputClass()}
      >
        {options.map((option) => (
          <option key={option}>{option}</option>
        ))}
      </select>
    </label>
  );
}

export function ToggleRow({ label, description, checked, onChange }) {
  return (
    <label className="flex items-start justify-between gap-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
      <span>
        <span className="block text-sm font-semibold text-slate-950">{label}</span>
        {description ? (
          <span className="mt-1 block text-sm leading-6 text-slate-600">{description}</span>
        ) : null}
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-700 focus:ring-blue-200"
      />
    </label>
  );
}

export function EmptyState({ title, text, action }) {
  return (
    <section className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
      <h2 className="text-base font-semibold text-slate-950">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">{text}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </section>
  );
}

export function TableShell({ caption, columns, children }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full text-left">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-slate-50">
          <tr>
            {columns.map((column) => (
              <th key={column} className="px-5 py-3 text-xs font-semibold uppercase text-slate-500">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">{children}</tbody>
      </table>
    </div>
  );
}

export function Drawer({ title, subtitle, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-950/30" role="dialog" aria-modal="true">
      <div className="ml-auto flex h-full w-full max-w-xl flex-col bg-white shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div>
            {subtitle ? (
              <p className="text-xs font-semibold uppercase text-slate-500">{subtitle}</p>
            ) : null}
            <h2 className="mt-1 text-lg font-semibold text-slate-950">{title}</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 focus:outline-none focus:ring-4 focus:ring-blue-100"
            aria-label="Close panel"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
      </div>
    </div>
  );
}

export function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/30 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-xl rounded-xl border border-slate-200 bg-white p-5 shadow-clinical">
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100 focus:outline-none focus:ring-4 focus:ring-blue-100"
            aria-label="Close dialog"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  );
}

export function StatePanel({ title, text, action }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="text-base font-semibold text-slate-950">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-slate-600">{text}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </section>
  );
}

export function inputClass(extra = "") {
  return `h-11 w-full rounded-lg border border-slate-300 bg-white px-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-700 focus:ring-4 focus:ring-blue-100 ${extra}`;
}

export function go(path) {
  window.location.assign(path);
}

export function getPatientId() {
  return window.location.pathname.split("/")[2] || "";
}

export function useScopedPatient() {
  return window.location.pathname.startsWith("/patients/")
    ? platformPatient
    : null;
}
