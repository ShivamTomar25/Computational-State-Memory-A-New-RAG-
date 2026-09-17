import { useState } from "react";
import {
  ArrowLeft,
  CalendarDays,
  Loader2,
  Save,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { getStoredDoctor } from "../login_page/authApi";
import { createPatient } from "../patient_shared/patientApi";

const initialFormData = {
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

const sexOptions = [
  { value: "", label: "Select sex" },
  { value: "female", label: "Female" },
  { value: "male", label: "Male" },
  { value: "other", label: "Other" },
  { value: "unknown", label: "Unknown" },
];

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function CreatePatientPage() {
  const [formData, setFormData] = useState(initialFormData);
  const [fieldErrors, setFieldErrors] = useState({});
  const [requestError, setRequestError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const doctor = getStoredDoctor();

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

  function validateForm() {
    const errors = {};
    const patientCode = formData.patientCode.trim();
    const fullName = formData.fullName.trim();
    const email = formData.email.trim();

    if (!patientCode) {
      errors.patientCode = "Enter a patient code.";
    } else if (patientCode.length > 50) {
      errors.patientCode = "Patient code must be 50 characters or fewer.";
    }

    if (!fullName) {
      errors.fullName = "Enter the patient name.";
    } else if (fullName.length < 2) {
      errors.fullName = "Patient name is too short.";
    }

    if (formData.dateOfBirth) {
      const dateOfBirth = new Date(`${formData.dateOfBirth}T00:00:00`);
      const today = new Date();

      if (Number.isNaN(dateOfBirth.getTime())) {
        errors.dateOfBirth = "Enter a valid date.";
      } else if (dateOfBirth > today) {
        errors.dateOfBirth = "Date of birth cannot be in the future.";
      }
    }

    if (email && !emailPattern.test(email)) {
      errors.email = "Use a valid email address.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setRequestError(null);

    if (!validateForm()) {
      return;
    }

    try {
      setIsSubmitting(true);

      const patient = await createPatient({
        patient_code: formData.patientCode,
        full_name: formData.fullName,
        date_of_birth: formData.dateOfBirth || null,
        sex: formData.sex || null,
        phone: formData.phone.trim() || null,
        email: formData.email.trim() || null,
        address: formData.address.trim() || null,
        emergency_contact_name: formData.emergencyContactName.trim() || null,
        emergency_contact_phone: formData.emergencyContactPhone.trim() || null,
      });

      window.location.assign(`/patients/${patient.id}`);
    } catch (error) {
      setRequestError(
        error instanceof Error
          ? error.message
          : "Unable to create the patient.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleCancel() {
    window.location.assign("/patients");
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8">
          <button
            type="button"
            onClick={handleCancel}
            disabled={isSubmitting}
            className="flex items-center gap-3 rounded-lg focus:outline-none focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-700 text-white">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
            </div>

            <div className="hidden text-left sm:block">
              <p className="text-sm font-semibold text-slate-950">Sustha</p>
              <p className="text-xs text-slate-500">Clinical workspace</p>
            </div>
          </button>

          <div className="text-right">
            <p className="text-sm font-medium text-slate-950">
              {doctor?.full_name ?? "Doctor"}
            </p>
            <p className="text-xs text-slate-500">
              {doctor?.email ?? "Signed-in doctor"}
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-5 py-8 sm:px-8">
        <nav
          aria-label="Breadcrumb"
          className="mb-6 flex items-center gap-2 text-sm text-slate-500"
        >
          <button
            type="button"
            onClick={handleCancel}
            disabled={isSubmitting}
            className="rounded text-slate-500 transition hover:text-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Patients
          </button>

          <span aria-hidden="true">/</span>

          <span className="font-medium text-slate-700">Create patient</span>
        </nav>

        <section className="mb-7">
          <button
            type="button"
            onClick={handleCancel}
            disabled={isSubmitting}
            className="mb-5 inline-flex items-center gap-2 rounded text-sm font-medium text-slate-600 transition hover:text-slate-950 focus:outline-none focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Back to patients
          </button>

          <h1 className="text-2xl font-semibold text-slate-950">
            Create patient
          </h1>

          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Add the patient identity and contact details. Documents and deeper
            clinical history can be added later.
          </p>
        </section>

        <form onSubmit={handleSubmit} noValidate>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            <section className="p-6 sm:p-8">
              <SectionHeading
                icon={<UserRound className="h-5 w-5" aria-hidden="true" />}
                title="Patient identity"
                description="Core information used to identify the patient."
              />

              <div className="mt-6 grid gap-5 sm:grid-cols-2">
                <FormField
                  label="Patient code"
                  htmlFor="patient-code"
                  required
                  error={fieldErrors.patientCode}
                  hint="Unique inside your patient list, for example PAT-000001."
                >
                  <input
                    id="patient-code"
                    type="text"
                    value={formData.patientCode}
                    onChange={(event) =>
                      updateField("patientCode", event.target.value)
                    }
                    placeholder="PAT-000001"
                    maxLength={50}
                    disabled={isSubmitting}
                    className={inputClass(Boolean(fieldErrors.patientCode))}
                  />
                </FormField>

                <FormField
                  label="Full name"
                  htmlFor="full-name"
                  required
                  error={fieldErrors.fullName}
                >
                  <input
                    id="full-name"
                    type="text"
                    autoComplete="name"
                    value={formData.fullName}
                    onChange={(event) =>
                      updateField("fullName", event.target.value)
                    }
                    placeholder="Enter full name"
                    maxLength={150}
                    disabled={isSubmitting}
                    className={inputClass(Boolean(fieldErrors.fullName))}
                  />
                </FormField>

                <FormField
                  label="Date of birth"
                  htmlFor="date-of-birth"
                  error={fieldErrors.dateOfBirth}
                >
                  <div className="relative">
                    <CalendarDays
                      className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
                      aria-hidden="true"
                    />
                    <input
                      id="date-of-birth"
                      type="date"
                      value={formData.dateOfBirth}
                      max={new Date().toISOString().split("T")[0]}
                      onChange={(event) =>
                        updateField("dateOfBirth", event.target.value)
                      }
                      disabled={isSubmitting}
                      className={`${inputClass(
                        Boolean(fieldErrors.dateOfBirth),
                      )} pl-10`}
                    />
                  </div>
                </FormField>

                <FormField label="Sex" htmlFor="sex">
                  <select
                    id="sex"
                    value={formData.sex}
                    onChange={(event) => updateField("sex", event.target.value)}
                    disabled={isSubmitting}
                    className={inputClass(false)}
                  >
                    {sexOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </FormField>
              </div>
            </section>

            <div className="border-t border-slate-200" />

            <section className="p-6 sm:p-8">
              <SectionHeading
                icon={<UserRound className="h-5 w-5" aria-hidden="true" />}
                title="Contact details"
                description="Optional contact and emergency contact information."
              />

              <div className="mt-6 grid gap-5 sm:grid-cols-2">
                <FormField label="Phone" htmlFor="phone">
                  <input
                    id="phone"
                    type="tel"
                    value={formData.phone}
                    onChange={(event) => updateField("phone", event.target.value)}
                    placeholder="+91 98765 43210"
                    maxLength={50}
                    disabled={isSubmitting}
                    className={inputClass(false)}
                  />
                </FormField>

                <FormField label="Email" htmlFor="email" error={fieldErrors.email}>
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    value={formData.email}
                    onChange={(event) => updateField("email", event.target.value)}
                    placeholder="patient@example.com"
                    disabled={isSubmitting}
                    className={inputClass(Boolean(fieldErrors.email))}
                  />
                </FormField>

                <FormField label="Emergency contact name" htmlFor="emergency-contact-name">
                  <input
                    id="emergency-contact-name"
                    type="text"
                    value={formData.emergencyContactName}
                    onChange={(event) =>
                      updateField("emergencyContactName", event.target.value)
                    }
                    maxLength={150}
                    disabled={isSubmitting}
                    className={inputClass(false)}
                  />
                </FormField>

                <FormField label="Emergency contact phone" htmlFor="emergency-contact-phone">
                  <input
                    id="emergency-contact-phone"
                    type="tel"
                    value={formData.emergencyContactPhone}
                    onChange={(event) =>
                      updateField("emergencyContactPhone", event.target.value)
                    }
                    maxLength={50}
                    disabled={isSubmitting}
                    className={inputClass(false)}
                  />
                </FormField>

                <FormField label="Address" htmlFor="address">
                  <textarea
                    id="address"
                    rows={4}
                    value={formData.address}
                    onChange={(event) =>
                      updateField("address", event.target.value)
                    }
                    maxLength={2000}
                    disabled={isSubmitting}
                    className={`${inputClass(false)} h-auto resize-y py-3 sm:col-span-2`}
                  />
                </FormField>
              </div>
            </section>

            {requestError ? (
              <div className="border-t border-red-200 bg-red-50 px-6 py-4 sm:px-8">
                <p role="alert" className="text-sm text-red-700">
                  {requestError}
                </p>
              </div>
            ) : null}

            <footer className="flex flex-col-reverse gap-3 border-t border-slate-200 bg-slate-50 px-6 py-4 sm:flex-row sm:justify-end sm:px-8">
              <button
                type="button"
                onClick={handleCancel}
                disabled={isSubmitting}
                className="inline-flex h-11 items-center justify-center rounded-lg border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 focus:outline-none focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Cancel
              </button>

              <button
                type="submit"
                disabled={isSubmitting}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-blue-700 px-5 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? (
                  <>
                    <Loader2
                      className="h-4 w-4 animate-spin"
                      aria-hidden="true"
                    />
                    Creating patient...
                  </>
                ) : (
                  <>
                    <Save className="h-4 w-4" aria-hidden="true" />
                    Create patient
                  </>
                )}
              </button>
            </footer>
          </div>
        </form>
      </main>
    </div>
  );
}

function SectionHeading({ icon, title, description }) {
  return (
    <div className="flex gap-3">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
        {icon}
      </div>

      <div>
        <h2 className="text-base font-semibold text-slate-950">{title}</h2>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
    </div>
  );
}

function FormField({ label, htmlFor, required, error, hint, children }) {
  return (
    <div>
      <label
        htmlFor={htmlFor}
        className="mb-2 block text-sm font-medium text-slate-700"
      >
        {label}
        {required ? (
          <span className="ml-1 text-red-600" aria-hidden="true">
            *
          </span>
        ) : null}
      </label>

      {children}

      {error ? (
        <p className="mt-1.5 text-xs text-red-600" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="mt-1.5 text-xs text-slate-500">{hint}</p>
      ) : null}
    </div>
  );
}

function inputClass(hasError) {
  return [
    "h-11 w-full rounded-lg border bg-white px-3.5 text-sm text-slate-900",
    "outline-none transition placeholder:text-slate-400",
    "focus:ring-4 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500",
    hasError
      ? "border-red-400 focus:border-red-500 focus:ring-red-100"
      : "border-slate-300 focus:border-blue-700 focus:ring-blue-100",
  ].join(" ");
}
