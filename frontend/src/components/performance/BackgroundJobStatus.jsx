export function BackgroundJobStatus({ status, label = "Background job" }) {
  if (!status) {
    return null;
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
      <span className="font-semibold text-slate-800">{label}</span>: {status}
    </div>
  );
}
