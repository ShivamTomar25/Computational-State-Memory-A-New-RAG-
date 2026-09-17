import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  ArrowLeft,
  BookOpenText,
  ChevronDown,
  Database,
  FilePlus2,
  Loader2,
  LogOut,
  MessageSquareText,
  Pencil,
  Plus,
  RotateCcw,
  Save,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import {
  clearAuthSession,
  getCurrentDoctor,
  getStoredDoctor,
} from "../login_page/authApi";
import { navigateInstant } from "../../performance/prefetch";
import { invalidatePatient } from "../../query/invalidation";
import { queryKeys } from "../../query/queryKeys";
import {
  archivePatient,
  restorePatient,
  updatePatient,
} from "../patient_shared/patientApi";
import { getPatientWorkspaceSummary } from "./workspaceApi";

const navigationItems = [
  "Overview",
  "Chat",
  "Documents",
  "Timeline",
  "Patient Information",
  "Memory Systems",
];

const sexOptions = [
  { value: "", label: "Not recorded" },
  { value: "female", label: "Female" },
  { value: "male", label: "Male" },
  { value: "other", label: "Other" },
  { value: "unknown", label: "Unknown" },
];

export function PatientWorkspacePage() {
  const patientId = getPatientId();
  const queryClient = useQueryClient();
  const [doctor, setDoctor] = useState(() => getStoredDoctor());
  const [patient, setPatient] = useState(null);
  const [formData, setFormData] = useState(emptyFormData);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [requestError, setRequestError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const workspaceQuery = useQuery({
    queryKey: queryKeys.patients.workspace(patientId),
    queryFn: () => getPatientWorkspaceSummary(patientId),
    enabled: Boolean(patientId),
  });

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
    if (workspaceQuery.data?.patient) {
      setPatient(workspaceQuery.data.patient);
      setRequestError(null);

      if (!isEditing) {
        setFormData(toFormData(workspaceQuery.data.patient));
      }
    }
  }, [workspaceQuery.data, isEditing]);

  useEffect(() => {
    if (workspaceQuery.error) {
      setRequestError(
        workspaceQuery.error instanceof Error
          ? workspaceQuery.error.message
          : "Unable to load patient.",
      );
    }
  }, [workspaceQuery.error]);

  function goToPatients() {
    navigateTo("/patients");
  }

  function logout() {
    clearAuthSession();
    window.location.assign("/");
  }

  function goToSection(section) {
    navigateTo(`/patients/${patientId}/${section}`);
  }

  function goToWorkspaceTab(item) {
    const routes = {
      Overview: `/patients/${patientId}`,
      Chat: `/patients/${patientId}/chat`,
      Documents: `/patients/${patientId}/documents`,
      Timeline: `/patients/${patientId}/timeline`,
      "Patient Information": `/patients/${patientId}/information`,
      "Memory Systems": `/patients/${patientId}/memory-systems`,
    };

    navigateTo(routes[item]);
  }

  function updateField(field, value) {
    setFormData((current) => ({
      ...current,
      [field]: value,
    }));
    setFieldErrors((current) => ({
      ...current,
      [field]: undefined,
    }));
    setRequestError(null);
  }

  async function savePatient(event) {
    event.preventDefault();
    setRequestError(null);

    const errors = validateForm(formData);
    setFieldErrors(errors);

    if (Object.keys(errors).length > 0) {
      return;
    }

    try {
      setIsSaving(true);
      const updatedPatient = await updatePatient(patientId, toUpdatePayload(formData));
      setPatient(updatedPatient);
      setFormData(toFormData(updatedPatient));
      queryClient.setQueryData(queryKeys.patients.workspace(patientId), (current) =>
        current ? { ...current, patient: updatedPatient } : current,
      );
      invalidatePatient(patientId);
      setIsEditing(false);
    } catch (error) {
      setRequestError(
        error instanceof Error ? error.message : "Unable to update patient.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function changeArchiveStatus() {
    if (!patient) {
      return;
    }

    try {
      setIsSaving(true);
      const updatedPatient = patient.is_active
        ? await archivePatient(patient.id)
        : await restorePatient(patient.id);
      setPatient(updatedPatient);
      setFormData(toFormData(updatedPatient));
      queryClient.setQueryData(queryKeys.patients.workspace(patientId), (current) =>
        current ? { ...current, patient: updatedPatient } : current,
      );
      invalidatePatient(patientId);
    } catch (error) {
      setRequestError(
        error instanceof Error
          ? error.message
          : "Unable to update patient status.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  const doctorName = doctor?.full_name ?? "Doctor";
  const isLoading = workspaceQuery.isLoading && !patient;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8">
          <button
            type="button"
            onClick={goToPatients}
            className="flex items-center gap-3 rounded-lg focus:outline-none focus:ring-4 focus:ring-blue-100"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-700 text-white">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="hidden text-left sm:block">
              <p className="text-sm font-semibold text-slate-950">
                Medical Memory Platform
              </p>
              <p className="text-xs text-slate-500">Patient workspace</p>
            </div>
          </button>

          <div className="flex items-center gap-2 sm:gap-4">
            <button
              type="button"
              onClick={() => navigateTo("/settings")}
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
        <button
          type="button"
          onClick={goToPatients}
          className="mb-5 inline-flex items-center gap-2 rounded text-sm font-medium text-slate-600 transition hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-blue-100"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to patients
        </button>

        {isLoading ? (
          <div className="rounded-xl border border-slate-200 bg-white px-6 py-12 text-center text-sm text-slate-500">
            Loading patient...
          </div>
        ) : null}

        {!isLoading && requestError && !patient ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-6 py-5 text-sm text-red-700">
            {requestError}
          </div>
        ) : null}

        {!isLoading && patient ? (
          <>
            <nav
              aria-label="Breadcrumb"
              className="mb-5 flex items-center gap-2 text-sm text-slate-500"
            >
              <button
                type="button"
                onClick={goToPatients}
                className="rounded transition hover:text-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-100"
              >
                Patients
              </button>
              <span aria-hidden="true">/</span>
              <span className="font-medium text-slate-700">
                {patient.full_name}
              </span>
            </nav>

            <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
              <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-3">
                    <h1 className="text-2xl font-semibold text-slate-950">
                      {patient.full_name}
                    </h1>
                    <StatusBadge active={patient.is_active} />
                  </div>

                  <p className="mt-2 text-sm font-medium text-slate-600">
                    {patient.patient_code}
                  </p>

                  <div className="mt-4 grid gap-2 text-sm text-slate-600 sm:grid-cols-2">
                    <p>{formatDemographics(patient)}</p>
                    <p>Last updated: {formatDateTime(patient.updated_at)}</p>
                    <p>Phone: {patient.phone || "Not recorded"}</p>
                    <p>Email: {patient.email || "Not recorded"}</p>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[560px]">
                  <ActionButton
                    icon={<Pencil className="h-4 w-4" aria-hidden="true" />}
                    label="Edit Patient"
                    onClick={() => setIsEditing(true)}
                    variant="secondary"
                  />
                  <ActionButton
                    icon={
                      patient.is_active ? (
                        <Archive className="h-4 w-4" aria-hidden="true" />
                      ) : (
                        <RotateCcw className="h-4 w-4" aria-hidden="true" />
                      )
                    }
                    label={patient.is_active ? "Archive Patient" : "Restore Patient"}
                    onClick={changeArchiveStatus}
                    disabled={isSaving}
                    variant="secondary"
                  />
                  <ActionButton
                    icon={<FilePlus2 className="h-4 w-4" aria-hidden="true" />}
                    label="Upload Document"
                    onClick={() => goToSection("documents")}
                    variant="secondary"
                  />
                  <ActionButton
                    icon={<Plus className="h-4 w-4" aria-hidden="true" />}
                    label="Add Patient Information"
                    onClick={() => goToSection("information")}
                    variant="secondary"
                  />
                  <ActionButton
                    icon={
                      <MessageSquareText className="h-4 w-4" aria-hidden="true" />
                    }
                    label="Start Chat"
                    onClick={() => goToSection("chat")}
                    onFocus={preloadChatPage}
                    onMouseEnter={preloadChatPage}
                    variant="secondary"
                  />
                  <ActionButton
                    icon={<Database className="h-4 w-4" aria-hidden="true" />}
                    label="Computational State"
                    onClick={() => goToSection("csm")}
                    variant="secondary"
                  />
                </div>
              </div>
            </section>

            {requestError ? (
              <div className="mt-6 rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
                {requestError}
              </div>
            ) : null}

            <nav className="mt-6 overflow-x-auto border-b border-slate-200">
              <div className="flex min-w-max gap-1">
                {navigationItems.map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => goToWorkspaceTab(item)}
                    className={`h-11 whitespace-nowrap border-b-2 px-4 text-sm font-medium ${
                      item === "Overview"
                        ? "border-blue-700 text-blue-700"
                        : "border-transparent text-slate-600 hover:text-slate-950"
                    }`}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </nav>

            <section className="mt-8 grid gap-6 lg:grid-cols-[1fr_0.9fr]">
              <PatientDetails patient={patient} />
              <PatientNextSteps patientId={patient.id} />
            </section>
          </>
        ) : null}
      </main>

      {isEditing ? (
        <EditPatientPanel
          formData={formData}
          fieldErrors={fieldErrors}
          isSaving={isSaving}
          onChange={updateField}
          onClose={() => {
            setIsEditing(false);
            setFormData(toFormData(patient));
            setFieldErrors({});
          }}
          onSubmit={savePatient}
        />
      ) : null}
    </div>
  );
}

function PatientDetails({ patient }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-base font-semibold text-slate-950">
          Patient Details
        </h2>
      </div>

      <dl className="grid gap-4 p-5 text-sm sm:grid-cols-2">
        <InfoRow label="Patient code" value={patient.patient_code} />
        <InfoRow label="Full name" value={patient.full_name} />
        <InfoRow label="Date of birth" value={formatDate(patient.date_of_birth)} />
        <InfoRow label="Sex" value={capitalize(patient.sex)} />
        <InfoRow label="Phone" value={patient.phone} />
        <InfoRow label="Email" value={patient.email} />
        <InfoRow label="Emergency contact" value={patient.emergency_contact_name} />
        <InfoRow label="Emergency phone" value={patient.emergency_contact_phone} />
        <InfoRow label="Created" value={formatDateTime(patient.created_at)} />
        <InfoRow label="Updated" value={formatDateTime(patient.updated_at)} />
        <div className="sm:col-span-2">
          <InfoRow label="Address" value={patient.address} />
        </div>
      </dl>
    </section>
  );
}

function PatientNextSteps({ patientId }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-base font-semibold text-slate-950">
          Next Steps
        </h2>
      </div>

      <div className="grid gap-3 p-5">
        <ActionButton
          icon={<FilePlus2 className="h-4 w-4" aria-hidden="true" />}
          label="Upload Document"
          onClick={() => navigateTo(`/patients/${patientId}/documents`)}
          variant="primary"
        />
        <ActionButton
          icon={<Plus className="h-4 w-4" aria-hidden="true" />}
          label="Add Patient Information"
          onClick={() => navigateTo(`/patients/${patientId}/information`)}
          variant="secondary"
        />
        <ActionButton
          icon={<BookOpenText className="h-4 w-4" aria-hidden="true" />}
          label="Evidence Explorer"
          onClick={() => navigateTo(`/patients/${patientId}/evidence`)}
          variant="secondary"
        />
        <ActionButton
          icon={<Database className="h-4 w-4" aria-hidden="true" />}
          label="Memory Systems"
          onClick={() => navigateTo(`/patients/${patientId}/memory-systems`)}
          variant="secondary"
        />
      </div>
    </section>
  );
}

function EditPatientPanel({
  formData,
  fieldErrors,
  isSaving,
  onChange,
  onClose,
  onSubmit,
}) {
  return (
    <div className="fixed inset-0 z-50 bg-slate-950/30" role="dialog" aria-modal="true">
      <div className="ml-auto flex h-full w-full max-w-2xl flex-col bg-white shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase text-slate-500">
              Patient profile
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-950">
              Edit Patient
            </h2>
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

        <form onSubmit={onSubmit} className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <TextField
                label="Patient code"
                value={formData.patientCode}
                error={fieldErrors.patientCode}
                onChange={(value) => onChange("patientCode", value)}
              />
              <TextField
                label="Full name"
                value={formData.fullName}
                error={fieldErrors.fullName}
                onChange={(value) => onChange("fullName", value)}
              />
              <TextField
                label="Date of birth"
                type="date"
                value={formData.dateOfBirth}
                error={fieldErrors.dateOfBirth}
                onChange={(value) => onChange("dateOfBirth", value)}
              />
              <SelectField
                label="Sex"
                value={formData.sex}
                onChange={(value) => onChange("sex", value)}
                options={sexOptions}
              />
              <TextField
                label="Phone"
                value={formData.phone}
                onChange={(value) => onChange("phone", value)}
              />
              <TextField
                label="Email"
                type="email"
                value={formData.email}
                error={fieldErrors.email}
                onChange={(value) => onChange("email", value)}
              />
              <TextField
                label="Emergency contact name"
                value={formData.emergencyContactName}
                onChange={(value) => onChange("emergencyContactName", value)}
              />
              <TextField
                label="Emergency contact phone"
                value={formData.emergencyContactPhone}
                onChange={(value) => onChange("emergencyContactPhone", value)}
              />
              <label className="block sm:col-span-2">
                <span className="mb-2 block text-sm font-medium text-slate-700">
                  Address
                </span>
                <textarea
                  rows={4}
                  value={formData.address}
                  onChange={(event) => onChange("address", event.target.value)}
                  className={inputClass("h-auto py-3")}
                />
              </label>
            </div>
          </div>

          <footer className="flex justify-end gap-3 border-t border-slate-200 bg-slate-50 px-5 py-4">
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="inline-flex h-10 items-center justify-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isSaving ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Save className="h-4 w-4" aria-hidden="true" />
              )}
              Save
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}

function TextField({ label, value, onChange, error, type = "text" }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={inputClass(error ? "border-red-400 focus:border-red-500 focus:ring-red-100" : "")}
      />
      {error ? <span className="mt-1 block text-xs text-red-600">{error}</span> : null}
    </label>
  );
}

function SelectField({ label, value, onChange, options }) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={inputClass()}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">
        {value || "Not recorded"}
      </dd>
    </div>
  );
}

function ActionButton({
  icon,
  label,
  onClick,
  disabled,
  variant,
  onFocus,
  onMouseEnter,
}) {
  const className =
    variant === "primary"
      ? "bg-blue-700 text-white hover:bg-blue-800 focus:ring-blue-200"
      : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus:ring-blue-100";

  return (
    <button
      type="button"
      onClick={onClick}
      onFocus={onFocus}
      onMouseEnter={onMouseEnter}
      disabled={disabled}
      className={`inline-flex h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold transition focus:outline-none focus:ring-4 disabled:cursor-not-allowed disabled:opacity-60 ${className}`}
    >
      {icon}
      {label}
    </button>
  );
}

function navigateTo(path) {
  navigateInstant(path);
  window.scrollTo({ top: 0, left: 0 });
}

function preloadChatPage() {
  import("../conversation_history/ConversationHistoryPage");
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

function getPatientId() {
  return window.location.pathname.split("/")[2];
}

function emptyFormData() {
  return {
    patientCode: "",
    fullName: "",
    dateOfBirth: "",
    sex: "",
    phone: "",
    email: "",
    address: "",
    emergencyContactName: "",
    emergencyContactPhone: "",
  };
}

function toFormData(patient) {
  if (!patient) {
    return emptyFormData();
  }

  return {
    patientCode: patient.patient_code ?? "",
    fullName: patient.full_name ?? "",
    dateOfBirth: patient.date_of_birth ?? "",
    sex: patient.sex ?? "",
    phone: patient.phone ?? "",
    email: patient.email ?? "",
    address: patient.address ?? "",
    emergencyContactName: patient.emergency_contact_name ?? "",
    emergencyContactPhone: patient.emergency_contact_phone ?? "",
  };
}

function toUpdatePayload(values) {
  return {
    patient_code: values.patientCode,
    full_name: values.fullName,
    date_of_birth: values.dateOfBirth || null,
    sex: values.sex || null,
    phone: values.phone.trim() || null,
    email: values.email.trim() || null,
    address: values.address.trim() || null,
    emergency_contact_name: values.emergencyContactName.trim() || null,
    emergency_contact_phone: values.emergencyContactPhone.trim() || null,
  };
}

function validateForm(values) {
  const errors = {};
  const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  if (!values.patientCode.trim()) {
    errors.patientCode = "Enter a patient code.";
  }

  if (!values.fullName.trim()) {
    errors.fullName = "Enter the patient name.";
  }

  if (values.dateOfBirth) {
    const dateOfBirth = new Date(`${values.dateOfBirth}T00:00:00`);
    const today = new Date();

    if (Number.isNaN(dateOfBirth.getTime())) {
      errors.dateOfBirth = "Enter a valid date.";
    } else if (dateOfBirth > today) {
      errors.dateOfBirth = "Date of birth cannot be in the future.";
    }
  }

  if (values.email.trim() && !emailPattern.test(values.email.trim())) {
    errors.email = "Use a valid email address.";
  }

  return errors;
}

function formatDemographics(patient) {
  const parts = [];

  if (patient.date_of_birth) {
    parts.push(`${calculateAge(patient.date_of_birth)} years`);
  }

  if (patient.sex) {
    parts.push(capitalize(patient.sex));
  }

  return parts.length > 0 ? parts.join(", ") : "Demographics not recorded";
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
    return null;
  }

  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function formatDateTime(value) {
  if (!value) {
    return null;
  }

  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function capitalize(value) {
  if (!value) {
    return null;
  }

  return value.charAt(0).toUpperCase() + value.slice(1);
}

function inputClass(extra = "") {
  return `h-11 w-full rounded-lg border border-slate-300 bg-white px-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-700 focus:ring-4 focus:ring-blue-100 ${extra}`;
}
