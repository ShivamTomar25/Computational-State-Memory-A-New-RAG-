import { ArrowLeft, FileSearch, ShieldCheck } from "lucide-react";

export function RagResponsePage() {
  const patientId = getPatientId();

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8">
          <button
            type="button"
            onClick={() => window.location.assign(`/patients/${patientId}`)}
            className="flex items-center gap-3 rounded-lg focus:outline-none focus:ring-4 focus:ring-blue-100"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-700 text-white">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="hidden text-left sm:block">
              <p className="text-sm font-semibold text-slate-950">Medical Memory Platform</p>
              <p className="text-xs text-slate-500">Grounded response details</p>
            </div>
          </button>
          <button
            type="button"
            onClick={() => window.location.assign(`/patients/${patientId}`)}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Patient
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-5 py-8 sm:px-8">
        <section className="rounded-xl border border-slate-200 bg-white p-8 text-center shadow-clinical">
          <FileSearch className="mx-auto h-10 w-10 text-slate-400" />
          <h1 className="mt-4 text-xl font-semibold text-slate-950">No response loaded</h1>
          <p className="mt-2 text-sm text-slate-600">
            Ask a question from a memory-system workspace to generate and inspect grounded response details.
          </p>
          <button
            type="button"
            onClick={() => window.location.assign(`/patients/${patientId}/compare`)}
            className="mt-5 inline-flex h-10 items-center justify-center rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white"
          >
            Open Memory Systems
          </button>
        </section>
      </main>
    </div>
  );
}

function getPatientId() {
  const segments = window.location.pathname.split("/").filter(Boolean);
  return segments[1] || "";
}
