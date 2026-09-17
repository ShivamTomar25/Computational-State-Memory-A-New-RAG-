import { Eye, EyeOff } from "lucide-react";

export function PasswordField({
  value,
  error,
  showPassword,
  onChange,
  onToggleVisibility,
}) {
  const describedBy = error ? "password-error" : undefined;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-4">
        <label htmlFor="password" className="text-sm font-medium text-slate-700">
          Password
        </label>

        <a
          href="/forgot-password"
          className="text-sm font-medium text-blue-700 transition hover:text-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-100"
        >
          Forgot password?
        </a>
      </div>

      <div className="relative">
        <input
          id="password"
          name="password"
          type={showPassword ? "text" : "password"}
          autoComplete="current-password"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          placeholder="Enter your password"
          className="h-11 w-full rounded-lg border border-slate-300 px-3.5 pr-12 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-700 focus:ring-4 focus:ring-blue-100"
        />

        <button
          type="button"
          onClick={onToggleVisibility}
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

      {error ? (
        <p id="password-error" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      ) : null}
    </div>
  );
}
