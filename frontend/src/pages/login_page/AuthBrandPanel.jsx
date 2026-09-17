import { CheckCircle2, ShieldCheck } from "lucide-react";

const trustPoints = [
  "Patient-specific memory",
  "Traceable medical evidence",
  "Secure clinical workflows",
];

export function AuthBrandPanel() {
  return (
    <section className="hidden border-r border-slate-200 bg-white px-12 py-14 lg:flex lg:flex-col lg:justify-between">
      <div>
        <BrandLockup />

        <div className="mt-24 max-w-xl">
          <p className="text-sm font-semibold uppercase tracking-[0.16em] text-blue-700">
            Clinical Memory Platform
          </p>

          <h1 className="mt-5 text-4xl font-semibold leading-tight text-slate-950">
            Evidence-grounded longitudinal intelligence for medical
            professionals.
          </h1>

          <p className="mt-6 max-w-lg text-base leading-7 text-slate-600">
            Sustha helps authorized clinicians return to patient context with
            clear source trails and low-friction clinical workflows.
          </p>

          <div className="mt-10 space-y-4">
            {trustPoints.map((point) => (
              <div key={point} className="flex items-center gap-3 text-sm">
                <CheckCircle2
                  className="h-5 w-5 text-green-700"
                  aria-hidden="true"
                />
                <span className="font-medium text-slate-700">{point}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className="text-xs text-slate-500">
        Authorized medical professionals only.
      </p>
    </section>
  );
}

export function BrandLockup() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-blue-700 text-white">
        <ShieldCheck className="h-6 w-6" aria-hidden="true" />
      </div>

      <div>
        <p className="text-lg font-semibold leading-6 text-slate-950">Sustha</p>
        <p className="text-sm text-slate-500">Clinical Intelligence</p>
      </div>
    </div>
  );
}
