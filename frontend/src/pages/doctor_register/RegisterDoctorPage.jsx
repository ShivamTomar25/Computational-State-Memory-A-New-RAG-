import { useState } from "react";
import { Eye, EyeOff, LoaderCircle, ShieldCheck } from "lucide-react";
import { loginDoctor, registerDoctor } from "../login_page/authApi";
import { BrandLockup } from "../login_page/AuthBrandPanel";
import { validateRegisterDoctorForm } from "./registerDoctorSchema";

const initialFormData = {
  fullName: "",
  email: "",
  password: "",
  specialization: "",
  medicalLicenseNumber: "",
  organizationName: "",
};

export function RegisterDoctorPage() {
  const [formData, setFormData] = useState(initialFormData);
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateField(key, value) {
    setFormData((current) => ({
      ...current,
      [key]: value,
    }));
    setFieldErrors((current) => ({
      ...current,
      [key]: undefined,
    }));
    setFormError(null);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setFormError(null);

    const validation = validateRegisterDoctorForm(formData);
    setFieldErrors(validation.errors);

    if (!validation.payload) {
      setFormError("Review the highlighted fields.");
      return;
    }

    try {
      setIsSubmitting(true);
      await registerDoctor(validation.payload);
      await loginDoctor({
        email: validation.payload.email,
        password: formData.password,
        rememberMe: true,
      });
      window.location.assign("/patients");
    } catch (requestError) {
      setFormError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to register this doctor.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-5 py-8 sm:px-8">
      <div className="mx-auto max-w-5xl">
        <div className="mb-8 flex items-center justify-between gap-4">
          <BrandLockup />

          <a
            href="/"
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
          >
            Sign in
          </a>
        </div>

        <section className="rounded-xl border border-slate-200 bg-white shadow-clinical">
          <div className="border-b border-slate-200 px-6 py-5 sm:px-8">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-700 text-white">
                <ShieldCheck className="h-5 w-5" aria-hidden="true" />
              </div>

              <div>
                <h1 className="text-xl font-semibold text-slate-950">
                  Create Doctor Account
                </h1>
                <p className="mt-1 text-sm text-slate-600">
                  Register a doctor profile for Sustha access.
                </p>
              </div>
            </div>
          </div>

          <form className="grid gap-5 px-6 py-6 sm:grid-cols-2 sm:px-8" onSubmit={handleSubmit} noValidate>
            <TextInput
              label="Full name"
              value={formData.fullName}
              error={fieldErrors.fullName}
              autoComplete="name"
              onChange={(value) => updateField("fullName", value)}
            />

            <TextInput
              label="Email address"
              type="email"
              value={formData.email}
              error={fieldErrors.email}
              autoComplete="email"
              onChange={(value) => updateField("email", value)}
            />

            <div>
              <div className="mb-2 flex items-center justify-between gap-4">
                <label htmlFor="doctor-register-password" className="text-sm font-medium text-slate-700">
                  Password
                </label>
              </div>

              <div className="relative">
                <input
                  id="doctor-register-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  value={formData.password}
                  onChange={(event) => updateField("password", event.target.value)}
                  aria-invalid={Boolean(fieldErrors.password)}
                  aria-describedby={fieldErrors.password ? "doctor-register-password-error" : undefined}
                  className="h-11 w-full rounded-lg border border-slate-300 px-3.5 pr-12 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-700 focus:ring-4 focus:ring-blue-100"
                />

                <button
                  type="button"
                  onClick={() => setShowPassword((current) => !current)}
                  className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-lg text-slate-500 transition hover:text-slate-700 focus:outline-none focus:ring-4 focus:ring-blue-100"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Eye className="h-4 w-4" aria-hidden="true" />
                  )}
                </button>
              </div>

              {fieldErrors.password ? (
                <p id="doctor-register-password-error" className="mt-2 text-sm text-red-700">
                  {fieldErrors.password}
                </p>
              ) : null}
            </div>

            <TextInput
              label="Specialization"
              value={formData.specialization}
              onChange={(value) => updateField("specialization", value)}
            />

            <TextInput
              label="Medical license number"
              value={formData.medicalLicenseNumber}
              onChange={(value) => updateField("medicalLicenseNumber", value)}
            />

            <TextInput
              label="Organization name"
              value={formData.organizationName}
              onChange={(value) => updateField("organizationName", value)}
            />

            <div className="sm:col-span-2">
              {formError ? (
                <div
                  role="alert"
                  className="mb-5 rounded-lg border border-red-200 bg-red-50 px-3.5 py-3 text-sm text-red-700"
                >
                  {formError}
                </div>
              ) : null}

              <button
                type="submit"
                disabled={isSubmitting}
                className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
              >
                {isSubmitting ? (
                  <>
                    <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />
                    Creating account...
                  </>
                ) : (
                  "Create Account"
                )}
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}

function TextInput({
  label,
  value,
  onChange,
  error,
  type = "text",
  autoComplete,
}) {
  const inputId = label.toLowerCase().replace(/\s+/g, "-");
  const errorId = error ? `${inputId}-error` : undefined;

  return (
    <div>
      <label htmlFor={inputId} className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={inputId}
        type={type}
        autoComplete={autoComplete}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={errorId}
        className="h-11 w-full rounded-lg border border-slate-300 px-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-700 focus:ring-4 focus:ring-blue-100"
      />
      {error ? (
        <p id={errorId} className="mt-2 text-sm text-red-700">
          {error}
        </p>
      ) : null}
    </div>
  );
}
