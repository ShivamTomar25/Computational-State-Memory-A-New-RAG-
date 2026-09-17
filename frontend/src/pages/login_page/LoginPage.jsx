import { AuthBrandPanel, BrandLockup } from "./AuthBrandPanel";
import { LoginForm } from "./LoginForm";

export function LoginPage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <div className="grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
        <AuthBrandPanel />

        <section className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-8">
          <div className="w-full max-w-[460px]">
            <div className="mb-8 lg:hidden">
              <BrandLockup />
            </div>

            <LoginForm />

            <div className="mt-4 grid gap-3">
              <a
                href="/patients"
                className="flex h-11 w-full items-center justify-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-4 focus:ring-blue-100"
              >
                Go to patients
              </a>

              <a
                href="/doctor-register"
                className="flex h-11 w-full items-center justify-center rounded-lg border border-blue-200 bg-blue-50 px-4 text-sm font-semibold text-blue-800 transition hover:bg-blue-100 focus:outline-none focus:ring-4 focus:ring-blue-100"
              >
                Create doctor account
              </a>
            </div>

            <p className="mt-6 text-center text-xs text-slate-500">
              Need access? Contact your system administrator.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
