import { useEffect, useState } from "react";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  LogOut,
  Plus,
  Search,
  ShieldCheck,
  UserRound,
  Users,
} from "lucide-react";
import {
  clearAuthSession,
  getCurrentDoctor,
  getStoredDoctor,
} from "../login_page/authApi";
import { navigateInstant } from "../../performance/prefetch";
import { listPatients } from "../patient_shared/patientApi";

const pageSize = 20;

const filterOptions = [
  { value: "active", label: "Active patients" },
  { value: "all", label: "Include archived" },
];

export function DoctorPatientsPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [filter, setFilter] = useState("active");
  const [doctor, setDoctor] = useState(() => getStoredDoctor());
  const [patients, setPatients] = useState([]);
  const [pagination, setPagination] = useState({
    total: 0,
    page: 1,
    page_size: pageSize,
    total_pages: 0,
  });
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [requestError, setRequestError] = useState(null);

  useEffect(() => {
    let isActive = true;

    getCurrentDoctor()
      .then((currentDoctor) => {
        if (isActive) {
          setDoctor(currentDoctor);
        }
      })
      .catch(() => {});

    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    let isActive = true;

    setIsLoading(true);
    setRequestError(null);

    listPatients({
      page,
      pageSize,
      search: searchQuery,
      includeArchived: filter === "all",
    })
      .then((data) => {
        if (isActive) {
          setPatients(data.items);
          setPagination({
            total: data.total,
            page: data.page,
            page_size: data.page_size,
            total_pages: data.total_pages,
          });
        }
      })
      .catch((error) => {
        if (isActive) {
          setPatients([]);
          setRequestError(
            error instanceof Error
              ? error.message
              : "Unable to load patients.",
          );
        }
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [searchQuery, filter, page]);

  function openPatient(patientId) {
    navigateInstant(`/patients/${patientId}`);
  }

  function logout() {
    clearAuthSession();
    window.location.assign("/");
  }

  function updateSearch(value) {
    setSearchQuery(value);
    setPage(1);
  }

  function updateFilter(value) {
    setFilter(value);
    setPage(1);
  }

  const doctorName = doctor?.full_name ?? "Doctor";
  const archivedOnPage = patients.filter((patient) => !patient.is_active).length;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-700 text-white">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
            </div>

            <div>
              <p className="text-sm font-semibold text-slate-950">Sustha</p>
              <p className="text-xs text-slate-500">Patients</p>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-4">
            <button
              type="button"
              onClick={() => navigateInstant("/settings")}
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

      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8">
        <section className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-950">
              Your Patients
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              View and manage patient records assigned to your account.
            </p>
          </div>

          <button
            type="button"
            onClick={() => navigateInstant("/create-patient")}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Create Patient
          </button>
        </section>

        <section className="mt-8 grid gap-4 sm:grid-cols-3">
          <SummaryCard
            icon={<Users className="h-5 w-5" aria-hidden="true" />}
            label="Matching patients"
            value={pagination.total}
          />
          <SummaryCard
            icon={<Clock3 className="h-5 w-5" aria-hidden="true" />}
            label="Page"
            value={`${pagination.page || 1}/${pagination.total_pages || 1}`}
          />
          <SummaryCard
            icon={<Users className="h-5 w-5" aria-hidden="true" />}
            label="Archived shown"
            value={archivedOnPage}
          />
        </section>

        <section className="mt-8 overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row">
            <div className="relative flex-1">
              <label htmlFor="patient-search" className="sr-only">
                Search patients
              </label>
              <Search
                className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                aria-hidden="true"
              />
              <input
                id="patient-search"
                type="search"
                value={searchQuery}
                onChange={(event) => updateSearch(event.target.value)}
                placeholder="Search by patient code, name, phone, or email"
                className="h-11 w-full rounded-lg border border-slate-300 pl-10 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-700 focus:ring-4 focus:ring-blue-100"
              />
            </div>

            <label htmlFor="patient-filter" className="sr-only">
              Filter patients
            </label>
            <select
              id="patient-filter"
              value={filter}
              onChange={(event) => updateFilter(event.target.value)}
              className="h-11 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 outline-none focus:border-blue-700 focus:ring-4 focus:ring-blue-100"
            >
              {filterOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {requestError ? (
            <div className="border-b border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
              {requestError}
            </div>
          ) : null}

          <div className="hidden overflow-x-auto md:block">
            <table className="min-w-full">
              <thead className="bg-slate-50">
                <tr>
                  <TableHeader>Patient</TableHeader>
                  <TableHeader>Demographics</TableHeader>
                  <TableHeader>Contact</TableHeader>
                  <TableHeader>Status</TableHeader>
                  <TableHeader>Updated</TableHeader>
                  <TableHeader>
                    <span className="sr-only">Open patient</span>
                  </TableHeader>
                </tr>
              </thead>

              <tbody className="divide-y divide-slate-200">
                {patients.map((patient) => (
                  <tr
                    key={patient.id}
                    onClick={() => openPatient(patient.id)}
                    className="cursor-pointer transition hover:bg-slate-50"
                  >
                    <td className="px-5 py-4">
                      <p className="text-sm font-medium text-slate-950">
                        {patient.full_name}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {patient.patient_code}
                      </p>
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600">
                      {formatDemographics(patient)}
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600">
                      {patient.phone || patient.email || "Not recorded"}
                    </td>
                    <td className="px-5 py-4">
                      <StatusBadge active={patient.is_active} />
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600">
                      {formatDate(patient.updated_at)}
                    </td>
                    <td className="px-5 py-4">
                      <ChevronRight
                        className="h-5 w-5 text-slate-400"
                        aria-hidden="true"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="divide-y divide-slate-200 md:hidden">
            {patients.map((patient) => (
              <button
                key={patient.id}
                type="button"
                onClick={() => openPatient(patient.id)}
                className="w-full p-5 text-left transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-inset focus:ring-blue-100"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold text-slate-950">
                      {patient.full_name}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      {patient.patient_code}
                    </p>
                  </div>
                  <ChevronRight
                    className="h-5 w-5 text-slate-400"
                    aria-hidden="true"
                  />
                </div>

                <p className="mt-3 text-sm text-slate-600">
                  {formatDemographics(patient)}
                </p>

                <div className="mt-4 flex items-center justify-between gap-4">
                  <StatusBadge active={patient.is_active} />
                  <span className="text-xs text-slate-500">
                    {formatDate(patient.updated_at)}
                  </span>
                </div>
              </button>
            ))}
          </div>

          {!isLoading && patients.length === 0 ? (
            <div className="px-5 py-16 text-center">
              <Users className="mx-auto h-10 w-10 text-slate-300" />
              <h2 className="mt-4 text-sm font-semibold text-slate-950">
                No patients found
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Try another search or create a new patient.
              </p>
            </div>
          ) : null}

          {isLoading ? (
            <div className="px-5 py-10 text-center text-sm text-slate-500">
              Loading patients...
            </div>
          ) : null}

          <footer className="flex items-center justify-between gap-4 border-t border-slate-200 px-5 py-4">
            <p className="text-sm text-slate-500">
              {pagination.total} total
            </p>

            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={page <= 1 || isLoading}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              </button>

              <button
                type="button"
                disabled={
                  isLoading ||
                  pagination.total_pages === 0 ||
                  page >= pagination.total_pages
                }
                onClick={() =>
                  setPage((current) =>
                    Math.min(pagination.total_pages, current + 1),
                  )
                }
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </footer>
        </section>
      </main>
    </div>
  );
}

function SummaryCard({ icon, label, value }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
        </div>
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
          {icon}
        </div>
      </div>
    </article>
  );
}

function TableHeader({ children }) {
  return (
    <th className="px-5 py-3 text-left text-xs font-semibold uppercase text-slate-500">
      {children}
    </th>
  );
}

function StatusBadge({ active }) {
  const className = active
    ? "border-green-200 bg-green-50 text-green-700"
    : "border-slate-200 bg-slate-50 text-slate-600";

  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${className}`}>
      {active ? "Active" : "Archived"}
    </span>
  );
}

function formatDemographics(patient) {
  const parts = [];

  if (patient.date_of_birth) {
    parts.push(`${calculateAge(patient.date_of_birth)} years`);
  }

  if (patient.sex) {
    parts.push(capitalize(patient.sex));
  }

  return parts.length > 0 ? parts.join(", ") : "Not recorded";
}

function calculateAge(dateOfBirth) {
  const birthDate = new Date(`${dateOfBirth}T00:00:00`);
  const today = new Date();
  let age = today.getFullYear() - birthDate.getFullYear();
  const monthDifference = today.getMonth() - birthDate.getMonth();

  if (
    monthDifference < 0 ||
    (monthDifference === 0 && today.getDate() < birthDate.getDate())
  ) {
    age -= 1;
  }

  return age;
}

function formatDate(value) {
  if (!value) {
    return "Not recorded";
  }

  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function capitalize(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
