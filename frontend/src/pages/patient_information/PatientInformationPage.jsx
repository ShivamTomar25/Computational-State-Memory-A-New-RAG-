import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  FileText,
  Loader2,
  LogOut,
  Pencil,
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
import { getPatient } from "../patient_shared/patientApi";
import {
  archivePatientInformation,
  createPatientInformation,
  listPatientInformation,
  restorePatientInformation,
  updatePatientInformation,
} from "./patientInformationApi";
import { cachePatientTimelineRecord } from "../patient_timeline/patientTimelineService";
import { cacheCsmRecord, syncCsm } from "../computational_state_memory/csmService";

const resourceOptions = [
  { value: "encounters", label: "Encounter" },
  { value: "conditions", label: "Condition" },
  { value: "medications", label: "Medication" },
  { value: "allergies", label: "Allergy" },
  { value: "measurements", label: "Measurement" },
  { value: "notes", label: "Clinical Note" },
];

const initialFormData = {
  title: "",
  details: "",
  status: "",
  secondaryStatus: "",
  category: "",
  eventDate: "",
  eventTime: "",
  valueNumeric: "",
  valueText: "",
  unit: "",
};

const navigationItems = [
  "Overview",
  "Chat",
  "Documents",
  "Timeline",
  "Patient Information",
  "Compare",
];

export function PatientInformationPage() {
  const patientId = getPatientId();
  const [doctor, setDoctor] = useState(() => getStoredDoctor());
  const [patient, setPatient] = useState(null);
  const [resource, setResource] = useState("conditions");
  const [records, setRecords] = useState([]);
  const [formData, setFormData] = useState(() => defaultFormData("conditions"));
  const [editingRecord, setEditingRecord] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [includeArchived, setIncludeArchived] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [requestError, setRequestError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const selectedResource = useMemo(
    () => resourceOptions.find((option) => option.value === resource),
    [resource],
  );

  useEffect(() => {
    let isActive = true;

    Promise.allSettled([getCurrentDoctor(), getPatient(patientId)])
      .then(([doctorResult, patientResult]) => {
        if (!isActive) {
          return;
        }

        if (doctorResult.status === "fulfilled") {
          setDoctor(doctorResult.value);
        }

        if (patientResult.status === "fulfilled") {
          setPatient(patientResult.value);
        } else {
          setRequestError(
            patientResult.reason instanceof Error
              ? patientResult.reason.message
              : "Unable to load patient.",
          );
        }
      });

    return () => {
      isActive = false;
    };
  }, [patientId]);

  useEffect(() => {
    loadRecords();
  }, [patientId, resource, includeArchived]);

  async function loadRecords() {
    setIsLoading(true);
    setRequestError(null);

    try {
      const data = await listPatientInformation(patientId, resource, includeArchived);
      setRecords(data.items);
    } catch (error) {
      setRecords([]);
      setRequestError(
        error instanceof Error
          ? error.message
          : "Unable to load patient information.",
      );
    } finally {
      setIsLoading(false);
    }
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
    setSuccessMessage(null);
  }

  function changeResource(value) {
    setResource(value);
    setFormData(defaultFormData(value));
    setEditingRecord(null);
    setFieldErrors({});
    setSuccessMessage(null);
  }

  function validateForm() {
    const errors = {};

    if (resource !== "notes" && !formData.title.trim()) {
      errors.title = "Enter the main clinical value.";
    }

    if (["encounters", "measurements", "notes"].includes(resource) && !formData.eventDate) {
      errors.eventDate = "Select the clinical date.";
    }

    if (resource === "measurements" && !formData.valueNumeric && !formData.valueText.trim()) {
      errors.value = "Enter a numeric or text value.";
    }

    if (resource === "notes" && !formData.details.trim()) {
      errors.details = "Enter note content.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(event) {
    event.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      setIsSaving(true);
      const payload = buildPayload(resource, formData);

      if (editingRecord) {
        const updatedRecord = await updatePatientInformation(patientId, resource, editingRecord.id, payload);
        cachePatientTimelineRecord(patientId, resource, updatedRecord);
        cacheCsmRecord(patientId, resource, updatedRecord);
        syncCsm(patientId).catch(() => {});
        setRecords((current) =>
          current.map((record) => (record.id === updatedRecord.id ? updatedRecord : record)),
        );
      } else {
        const createdRecord = await createPatientInformation(patientId, resource, payload);
        cachePatientTimelineRecord(patientId, resource, createdRecord);
        cacheCsmRecord(patientId, resource, createdRecord);
        syncCsm(patientId).catch(() => {});
        setRecords((current) => [createdRecord, ...current]);
      }

      setFormData(defaultFormData(resource));
      setEditingRecord(null);
      setSuccessMessage(
        `${selectedResource.label} ${editingRecord ? "updated" : "saved"}.`,
      );
      loadRecords();
    } catch (error) {
      setRequestError(
        error instanceof Error
          ? error.message
          : "Unable to save patient information.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  function startEditing(record) {
    setEditingRecord(record);
    setFormData(recordToFormData(resource, record));
    setFieldErrors({});
    setRequestError(null);
    setSuccessMessage(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function cancelEditing() {
    setEditingRecord(null);
    setFormData(defaultFormData(resource));
    setFieldErrors({});
    setRequestError(null);
    setSuccessMessage(null);
  }

  async function changeArchiveStatus(record) {
    try {
      setIsSaving(true);

      if (record.is_active) {
        await archivePatientInformation(patientId, resource, record.id);
      } else {
        await restorePatientInformation(patientId, resource, record.id);
      }

      await loadRecords();
    } catch (error) {
      setRequestError(
        error instanceof Error
          ? error.message
          : "Unable to update record visibility.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  function handleCancel() {
    window.location.assign(`/patients/${patientId}`);
  }

  function logout() {
    clearAuthSession();
    window.location.assign("/");
  }

  const doctorName = doctor?.full_name ?? "Doctor";

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8">
          <button
            type="button"
            onClick={handleCancel}
            className="flex items-center gap-3 rounded-lg focus:outline-none focus:ring-4 focus:ring-blue-100"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-700 text-white">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="hidden text-left sm:block">
              <p className="text-sm font-semibold text-slate-950">
                Medical Memory Platform
              </p>
              <p className="text-xs text-slate-500">Patient information</p>
            </div>
          </button>

          <div className="flex items-center gap-2 sm:gap-4">
            <button
              type="button"
              onClick={() => window.location.assign("/settings")}
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
          onClick={handleCancel}
          className="mb-5 inline-flex items-center gap-2 rounded text-sm font-medium text-slate-600 transition hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-blue-100"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to patient overview
        </button>

        <nav
          aria-label="Breadcrumb"
          className="mb-5 flex items-center gap-2 text-sm text-slate-500"
        >
          <button
            type="button"
            onClick={() => window.location.assign("/patients")}
            className="rounded transition hover:text-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-100"
          >
            Patients
          </button>
          <span aria-hidden="true">/</span>
          <button
            type="button"
            onClick={handleCancel}
            className="rounded transition hover:text-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-100"
          >
            {patient?.full_name ?? "Patient"}
          </button>
          <span aria-hidden="true">/</span>
          <span className="font-medium text-slate-700">Patient Information</span>
        </nav>

        <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
          <p className="text-sm font-medium text-slate-500">
            {patient?.patient_code ?? "Patient record"}
          </p>
          <h1 className="mt-2 text-2xl font-semibold text-slate-950">
            Patient Information
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
            Record structured encounters, conditions, medications, allergies,
            measurements, and clinical notes for this patient.
          </p>
          {patient ? (
            <p className="mt-3 text-sm text-slate-600">
              {patient.full_name} {patient.date_of_birth ? `- born ${formatDate(patient.date_of_birth)}` : ""}
            </p>
          ) : null}
        </section>

        <nav className="mt-6 overflow-x-auto border-b border-slate-200">
          <div className="flex min-w-max gap-1">
            {navigationItems.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => goToWorkspaceTab(patientId, item)}
                className={`h-11 whitespace-nowrap border-b-2 px-4 text-sm font-medium ${
                  item === "Patient Information"
                    ? "border-blue-700 text-blue-700"
                    : "border-transparent text-slate-600 hover:text-slate-950"
                }`}
              >
                {item}
              </button>
            ))}
          </div>
        </nav>

        {successMessage ? (
          <div className="mt-8 rounded-xl border border-green-200 bg-green-50 px-5 py-4">
            <div className="flex gap-3">
              <CheckCircle2 className="mt-0.5 h-5 w-5 text-green-700" />
              <p className="text-sm font-semibold text-green-800">
                {successMessage}
              </p>
            </div>
          </div>
        ) : null}

        {requestError ? (
          <div className="mt-8 rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
            {requestError}
          </div>
        ) : null}

        <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
          <form onSubmit={handleSubmit} className="rounded-xl border border-slate-200 bg-white">
            <div className="border-b border-slate-200 px-6 py-4">
              <h2 className="text-base font-semibold text-slate-950">
                {editingRecord ? `Edit ${selectedResource?.label}` : "Add Structured Information"}
              </h2>
            </div>

            <div className="space-y-5 p-6">
              <div className="grid gap-5 sm:grid-cols-2">
                <FormField label="Record type" htmlFor="record-type">
                  <select
                    id="record-type"
                    value={resource}
                    onChange={(event) => changeResource(event.target.value)}
                    disabled={Boolean(editingRecord)}
                    className={inputClass()}
                  >
                    {resourceOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </FormField>

                <FormField
                  label={titleLabel(resource)}
                  htmlFor="title"
                  error={fieldErrors.title}
                >
                  <input
                    id="title"
                    type="text"
                    value={formData.title}
                    onChange={(event) => updateField("title", event.target.value)}
                    className={inputClass(Boolean(fieldErrors.title))}
                  />
                </FormField>
              </div>

              <ResourceFields
                resource={resource}
                formData={formData}
                fieldErrors={fieldErrors}
                onChange={updateField}
              />

              <FormField
                label={resource === "notes" ? "Content" : "Notes or details"}
                htmlFor="details"
                error={fieldErrors.details}
              >
                <textarea
                  id="details"
                  rows={5}
                  value={formData.details}
                  onChange={(event) => updateField("details", event.target.value)}
                  className={`${inputClass(Boolean(fieldErrors.details))} h-auto resize-y py-3`}
                />
              </FormField>
            </div>

            <footer className="flex flex-col gap-3 border-t border-slate-200 bg-slate-50 px-6 py-4 sm:flex-row sm:justify-end">
              {editingRecord ? (
                <button
                  type="button"
                  onClick={cancelEditing}
                  disabled={isSaving}
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                  Cancel
                </button>
              ) : null}
              <button
                type="submit"
                disabled={isSaving}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-blue-700 px-5 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Save className="h-4 w-4" aria-hidden="true" />
                )}
                {editingRecord ? "Update" : "Save"} {selectedResource?.label}
              </button>
            </footer>
          </form>

          <aside className="rounded-xl border border-slate-200 bg-white">
            <div className="border-b border-slate-200 px-5 py-4">
              <h2 className="text-base font-semibold text-slate-950">
                Viewing
              </h2>
            </div>
            <div className="space-y-4 p-5">
              <div className="grid gap-2">
                {resourceOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => changeResource(option.value)}
                    className={`h-10 rounded-lg px-3 text-left text-sm font-semibold transition focus:outline-none focus:ring-4 focus:ring-blue-100 ${
                      resource === option.value
                        ? "bg-blue-700 text-white"
                        : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>

              <label className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={includeArchived}
                  onChange={(event) => setIncludeArchived(event.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-blue-700 focus:ring-blue-200"
                />
                Include archived records
              </label>
            </div>
          </aside>
        </section>

        <InformationHistory
          resource={resource}
          records={records}
          isLoading={isLoading}
          editingRecordId={editingRecord?.id}
          onEdit={startEditing}
          onArchiveToggle={changeArchiveStatus}
        />
      </main>
    </div>
  );
}

function ResourceFields({ resource, formData, fieldErrors, onChange }) {
  if (resource === "measurements") {
    return (
      <div className="grid gap-5 sm:grid-cols-3">
        <StatusField resource={resource} formData={formData} onChange={onChange} />
        <FormField label="Numeric value" htmlFor="value-numeric" error={fieldErrors.value}>
          <input id="value-numeric" type="number" step="any" value={formData.valueNumeric} onChange={(event) => onChange("valueNumeric", event.target.value)} className={inputClass(Boolean(fieldErrors.value))} />
        </FormField>
        <FormField label="Text value" htmlFor="value-text" error={fieldErrors.value}>
          <input id="value-text" type="text" value={formData.valueText} onChange={(event) => onChange("valueText", event.target.value)} className={inputClass(Boolean(fieldErrors.value))} />
        </FormField>
        <FormField label="Unit" htmlFor="unit">
          <input id="unit" type="text" value={formData.unit} onChange={(event) => onChange("unit", event.target.value)} className={inputClass()} />
        </FormField>
        <DateTimeFields formData={formData} fieldErrors={fieldErrors} onChange={onChange} label="Observed" />
      </div>
    );
  }

  if (resource === "encounters" || resource === "notes") {
    return (
      <div className="grid gap-5 sm:grid-cols-2">
        <StatusField
          resource={resource}
          formData={formData}
          onChange={onChange}
          label={resource === "notes" ? "Note type" : "Encounter type"}
        />
        <SecondaryStatusField
          resource={resource}
          formData={formData}
          onChange={onChange}
          label={resource === "notes" ? "Note status" : "Encounter status"}
        />
        <DateTimeFields formData={formData} fieldErrors={fieldErrors} onChange={onChange} label={resource === "notes" ? "Authored" : "Started"} />
      </div>
    );
  }

  return (
    <div className="grid gap-5 sm:grid-cols-3">
      <StatusField resource={resource} formData={formData} onChange={onChange} />
      <SecondaryStatusField
        resource={resource}
        formData={formData}
        onChange={onChange}
        label={resource === "conditions" ? "Verification" : "Secondary status"}
      />
      <FormField label="Category" htmlFor="category">
        <select id="category" value={formData.category} onChange={(event) => onChange("category", event.target.value)} className={inputClass()}>
          {categoryOptions(resource).map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </FormField>
      <FormField label="Clinical date" htmlFor="event-date" error={fieldErrors.eventDate}>
        <input id="event-date" type="date" value={formData.eventDate} onChange={(event) => onChange("eventDate", event.target.value)} className={inputClass(Boolean(fieldErrors.eventDate))} />
      </FormField>
    </div>
  );
}

function DateTimeFields({ formData, fieldErrors, onChange, label }) {
  return (
    <>
      <FormField label={`${label} date`} htmlFor="event-date" error={fieldErrors.eventDate}>
        <input id="event-date" type="date" value={formData.eventDate} onChange={(event) => onChange("eventDate", event.target.value)} className={inputClass(Boolean(fieldErrors.eventDate))} />
      </FormField>
      <FormField label={`${label} time`} htmlFor="event-time">
        <input id="event-time" type="time" value={formData.eventTime} onChange={(event) => onChange("eventTime", event.target.value)} className={inputClass()} />
      </FormField>
    </>
  );
}

function StatusField({ resource, formData, onChange, label = "Status" }) {
  return (
    <FormField label={label} htmlFor="status">
      <select id="status" value={formData.status} onChange={(event) => onChange("status", event.target.value)} className={inputClass()}>
        {statusOptions(resource).map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </FormField>
  );
}

function SecondaryStatusField({ resource, formData, onChange, label }) {
  return (
    <FormField label={label ?? "Secondary status"} htmlFor="secondary-status">
      <select
        id="secondary-status"
        value={formData.secondaryStatus}
        onChange={(event) => onChange("secondaryStatus", event.target.value)}
        className={inputClass()}
      >
        {secondaryStatusOptions(resource).map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </FormField>
  );
}

function InformationHistory({
  resource,
  records,
  isLoading,
  editingRecordId,
  onEdit,
  onArchiveToggle,
}) {
  return (
    <section className="mt-8 rounded-xl border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-base font-semibold text-slate-950">
          Existing {resourceLabel(resource)} Records
        </h2>
      </div>

      {isLoading ? (
        <div className="px-5 py-10 text-center text-sm text-slate-500">
          Loading records...
        </div>
      ) : null}

      {!isLoading && records.length === 0 ? (
        <div className="px-5 py-12 text-center">
          <FileText className="mx-auto h-10 w-10 text-slate-300" />
          <h3 className="mt-4 text-sm font-semibold text-slate-950">
            No records found
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Add the first structured record for this patient.
          </p>
        </div>
      ) : null}

      {records.length > 0 ? (
        <div className="divide-y divide-slate-200">
          {records.map((record) => (
            <article key={record.id} className="flex flex-col gap-4 p-5 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold text-slate-950">
                    {recordTitle(resource, record)}
                  </h3>
                  <Badge active={record.is_active} />
                </div>
                <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">
                  {recordSummary(resource, record)}
                </p>
                <p className="mt-2 text-xs text-slate-500">
                  {recordTime(resource, record)}
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => onEdit(record)}
                  className={`inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-semibold transition focus:outline-none focus:ring-4 focus:ring-blue-100 ${
                    editingRecordId === record.id
                      ? "border-blue-700 bg-blue-50 text-blue-700"
                      : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  <Pencil className="h-4 w-4" aria-hidden="true" />
                  Edit
                </button>

                <button
                  type="button"
                  onClick={() => onArchiveToggle(record)}
                  className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
                >
                  {record.is_active ? (
                    <Archive className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <RotateCcw className="h-4 w-4" aria-hidden="true" />
                  )}
                  {record.is_active ? "Archive" : "Restore"}
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function recordToFormData(resource, record) {
  if (resource === "encounters") {
    const event = splitDateTime(record.started_at);

    return {
      ...initialFormData,
      title: record.chief_complaint ?? "",
      details: record.summary ?? "",
      status: record.encounter_type ?? "",
      secondaryStatus: record.status ?? "",
      eventDate: event.date,
      eventTime: event.time,
    };
  }

  if (resource === "conditions") {
    return {
      ...initialFormData,
      title: record.name ?? "",
      details: record.notes ?? "",
      status: record.clinical_status ?? "",
      secondaryStatus: record.verification_status ?? "",
      category: record.category ?? "",
      eventDate: dateOnly(record.onset_date),
    };
  }

  if (resource === "medications") {
    return {
      ...initialFormData,
      title: record.medication_name ?? "",
      details: record.instructions ?? "",
      status: record.medication_status ?? "",
      eventDate: dateOnly(record.start_date),
    };
  }

  if (resource === "allergies") {
    return {
      ...initialFormData,
      title: record.substance ?? "",
      details: record.reaction ?? record.notes ?? "",
      status: record.clinical_status ?? "",
      secondaryStatus: record.verification_status ?? "",
      category: record.category ?? "",
      eventDate: dateOnly(record.onset_date),
    };
  }

  if (resource === "measurements") {
    const event = splitDateTime(record.observed_at);

    return {
      ...initialFormData,
      title: record.observation_name ?? "",
      details: record.notes ?? "",
      status: record.status ?? "",
      eventDate: event.date,
      eventTime: event.time,
      valueNumeric: record.value_numeric === null || record.value_numeric === undefined ? "" : String(record.value_numeric),
      valueText: record.value_text ?? "",
      unit: record.unit ?? "",
    };
  }

  const event = splitDateTime(record.authored_at);

  return {
    ...initialFormData,
    title: record.title ?? "",
    details: record.content ?? "",
    status: record.note_type ?? "",
    secondaryStatus: record.status ?? "",
    eventDate: event.date,
    eventTime: event.time,
  };
}

function defaultFormData(resource) {
  const defaults = {
    encounters: {
      status: "outpatient",
      secondaryStatus: "planned",
    },
    conditions: {
      status: "active",
      secondaryStatus: "confirmed",
      category: "diagnosis",
    },
    medications: {
      status: "active",
    },
    allergies: {
      status: "active",
      secondaryStatus: "confirmed",
      category: "medication",
    },
    measurements: {
      status: "final",
    },
    notes: {
      status: "progress",
      secondaryStatus: "draft",
    },
  };

  return {
    ...initialFormData,
    ...(defaults[resource] ?? {}),
  };
}

function buildPayload(resource, values) {
  const eventDateTime = toDateTime(values.eventDate, values.eventTime);

  if (resource === "encounters") {
    return {
      encounter_type: values.status || "outpatient",
      status: values.secondaryStatus || "planned",
      started_at: eventDateTime,
      chief_complaint: values.title,
      summary: values.details || null,
    };
  }

  if (resource === "conditions") {
    return {
      name: values.title,
      category: values.category || "diagnosis",
      clinical_status: values.status || "active",
      verification_status: values.secondaryStatus || "confirmed",
      onset_date: values.eventDate || null,
      notes: values.details || null,
    };
  }

  if (resource === "medications") {
    return {
      medication_name: values.title,
      medication_status: values.status || "active",
      start_date: values.eventDate || null,
      instructions: values.details || null,
    };
  }

  if (resource === "allergies") {
    return {
      substance: values.title,
      allergy_type: "allergy",
      category: values.category || null,
      clinical_status: values.status || "active",
      verification_status: values.secondaryStatus || "confirmed",
      reaction: values.details || null,
      onset_date: values.eventDate || null,
    };
  }

  if (resource === "measurements") {
    return {
      observation_name: values.title,
      value_numeric: values.valueNumeric ? Number(values.valueNumeric) : null,
      value_text: values.valueText || null,
      unit: values.unit || null,
      status: values.status || "final",
      observed_at: eventDateTime,
      notes: values.details || null,
    };
  }

  return {
    note_type: values.status || "progress",
    title: values.title || null,
    content: values.details,
    status: values.secondaryStatus || "draft",
    authored_at: eventDateTime,
  };
}

function titleLabel(resource) {
  const labels = {
    encounters: "Chief complaint",
    conditions: "Condition name",
    medications: "Medication name",
    allergies: "Substance",
    measurements: "Observation name",
    notes: "Note title",
  };

  return labels[resource];
}

function statusOptions(resource) {
  const options = {
    encounters: ["outpatient", "inpatient", "emergency", "telemedicine", "follow_up", "diagnostic", "other"],
    conditions: ["active", "inactive", "resolved", "remission", "recurrent", "unknown"],
    medications: ["planned", "active", "on_hold", "completed", "stopped", "cancelled", "entered_in_error", "unknown"],
    allergies: ["active", "inactive", "resolved"],
    measurements: ["preliminary", "final", "amended", "corrected", "cancelled", "entered_in_error"],
    notes: ["progress", "consultation", "discharge", "procedure", "assessment", "plan", "nursing", "administrative", "other"],
  };

  return toOptions(options[resource] ?? []);
}

function secondaryStatusOptions(resource) {
  const options = {
    encounters: ["planned", "in_progress", "completed", "cancelled"],
    conditions: ["suspected", "provisional", "confirmed", "refuted", "entered_in_error"],
    medications: ["active"],
    allergies: ["unconfirmed", "presumed", "confirmed", "refuted", "entered_in_error"],
    notes: ["draft", "final", "amended", "entered_in_error"],
  };

  return toOptions(options[resource] ?? ["confirmed"]);
}

function categoryOptions(resource) {
  const options = {
    conditions: ["diagnosis", "symptom", "problem", "history", "risk"],
    allergies: ["", "medication", "food", "environment", "biologic", "other"],
    medications: [""],
  };

  return toOptions(options[resource] ?? [""]);
}

function toOptions(values) {
  return values.map((value) => ({
    value,
    label: value ? value.replaceAll("_", " ") : "None",
  }));
}

function resourceLabel(resource) {
  return resourceOptions.find((option) => option.value === resource)?.label ?? "Clinical";
}

function recordTitle(resource, record) {
  if (resource === "encounters") return record.chief_complaint || record.encounter_type;
  if (resource === "conditions") return record.name;
  if (resource === "medications") return record.medication_name;
  if (resource === "allergies") return record.substance;
  if (resource === "measurements") return record.observation_name;
  return record.title || record.note_type;
}

function recordSummary(resource, record) {
  if (resource === "encounters") return record.summary || record.status;
  if (resource === "conditions") return `${record.category}, ${record.clinical_status}, ${record.verification_status}${record.notes ? ` - ${record.notes}` : ""}`;
  if (resource === "medications") return `${record.medication_status}${record.instructions ? ` - ${record.instructions}` : ""}`;
  if (resource === "allergies") return `${record.clinical_status}, ${record.verification_status}${record.reaction ? ` - ${record.reaction}` : ""}`;
  if (resource === "measurements") return `${record.value_numeric ?? record.value_text} ${record.unit ?? ""}`.trim();
  return record.content;
}

function recordTime(resource, record) {
  const value = record.started_at || record.observed_at || record.authored_at || record.recorded_at || record.created_at;
  return value ? formatDateTime(value) : "No clinical time recorded";
}

function toDateTime(dateValue, timeValue) {
  const date = dateValue || new Date().toISOString().split("T")[0];
  const time = timeValue || "00:00";

  return new Date(`${date}T${time}:00`).toISOString();
}

function splitDateTime(value) {
  if (!value) {
    return { date: "", time: "" };
  }

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return { date: "", time: "" };
  }

  const localTime = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000)
    .toISOString();

  return {
    date: localTime.slice(0, 10),
    time: localTime.slice(11, 16),
  };
}

function dateOnly(value) {
  return value ? String(value).slice(0, 10) : "";
}

function goToWorkspaceTab(patientId, item) {
  const routes = {
    Overview: `/patients/${patientId}`,
    Chat: `/patients/${patientId}/chat`,
    Documents: `/patients/${patientId}/documents`,
    Timeline: `/patients/${patientId}/timeline`,
    "Patient Information": `/patients/${patientId}/information`,
    Compare: `/patients/${patientId}/compare`,
  };

  window.location.assign(routes[item]);
}

function getPatientId() {
  return window.location.pathname.split("/")[2];
}

function formatDate(value) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function FormField({ label, htmlFor, error, children }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </label>
      {children}
      {error ? <p className="mt-1.5 text-xs text-red-600">{error}</p> : null}
    </div>
  );
}

function inputClass(hasError = false) {
  return [
    "h-11 w-full rounded-lg border bg-white px-3.5 text-sm text-slate-900",
    "outline-none transition placeholder:text-slate-400",
    "focus:ring-4 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500",
    hasError
      ? "border-red-400 focus:border-red-500 focus:ring-red-100"
      : "border-slate-300 focus:border-blue-700 focus:ring-blue-100",
  ].join(" ");
}

function Badge({ active }) {
  const className = active
    ? "border-green-200 bg-green-50 text-green-700"
    : "border-slate-200 bg-slate-50 text-slate-600";

  return (
    <span className={`inline-flex w-fit rounded-full border px-2.5 py-1 text-xs font-medium ${className}`}>
      {active ? "Active" : "Archived"}
    </span>
  );
}
