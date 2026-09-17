import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { loginDoctor } from "./authApi";
import { normalizeEmail, validateLoginForm } from "./loginSchema";
import { PasswordField } from "./PasswordField";

const initialFormData = {
  email: "",
  password: "",
  rememberMe: false,
};

export function LoginForm() {
  const [formData, setFormData] = useState(initialFormData);
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setFormError(null);

    const validation = validateLoginForm(formData);
    setFieldErrors(validation.errors);

    if (!validation.payload) {
      setFormError(
        validation.errors.email ??
          validation.errors.password ??
          "Review the highlighted fields.",
      );
      return;
    }

    try {
      setIsSubmitting(true);
      await loginDoctor(validation.payload);
      window.location.assign("/patients");
    } catch (requestError) {
      setFormError(
        requestError instanceof Error
          ? requestError.message
          : "Unable to sign in.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

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

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-7 shadow-clinical sm:p-9">
      <header>
        <h2 className="text-2xl font-semibold text-slate-950">Welcome back</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Sign in to access your clinical workspace.
        </p>
      </header>

      <form className="mt-8 space-y-5" onSubmit={handleSubmit} noValidate>
        <div>
          <label
            htmlFor="doctor-email"
            className="mb-2 block text-sm font-medium text-slate-700"
          >
            Email address
          </label>

          <input
            id="doctor-email"
            name="email"
            type="email"
            autoComplete="username"
            inputMode="email"
            value={formData.email}
            onBlur={() =>
              setFormData((current) => ({
                ...current,
                email: normalizeEmail(current.email),
              }))
            }
            onChange={(event) => updateField("email", event.target.value)}
            aria-invalid={Boolean(fieldErrors.email)}
            aria-describedby={
              fieldErrors.email ? "doctor-email-error" : undefined
            }
            placeholder="doctor@sustha.example"
            className="h-11 w-full rounded-lg border border-slate-300 px-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-700 focus:ring-4 focus:ring-blue-100"
          />

          {fieldErrors.email ? (
            <p id="doctor-email-error" className="mt-2 text-sm text-red-700">
              {fieldErrors.email}
            </p>
          ) : null}
        </div>

        <PasswordField
          value={formData.password}
          error={fieldErrors.password}
          showPassword={showPassword}
          onChange={(value) => updateField("password", value)}
          onToggleVisibility={() => setShowPassword((current) => !current)}
        />

        <label className="flex cursor-pointer items-center gap-2.5">
          <input
            type="checkbox"
            checked={formData.rememberMe}
            onChange={(event) => updateField("rememberMe", event.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-blue-700 focus:ring-blue-600"
          />

          <span className="text-sm text-slate-600">
            Keep me signed in on this device
          </span>
        </label>

        {formError ? (
          <div
            role="alert"
            className="rounded-lg border border-red-200 bg-red-50 px-3.5 py-3 text-sm text-red-700"
          >
            {formError}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={isSubmitting}
          className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? (
            <>
              <LoaderCircle
                className="h-4 w-4 animate-spin"
                aria-hidden="true"
              />
              Signing in...
            </>
          ) : (
            "Sign in"
          )}
        </button>
      </form>

      <div className="mt-7 border-t border-slate-200 pt-5">
        <p className="text-center text-xs leading-5 text-slate-500">
          Access is restricted to authorized medical professionals.
        </p>
      </div>
    </div>
  );
}
