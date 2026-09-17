import { EvaluationPanel } from "./EvaluationPanel";

export function ExperimentProgress({ progress, onStart, disabled }) {
  return (
    <EvaluationPanel title="Experiment Progress">
      {progress ? (
        <dl className="space-y-2 text-sm">
          <Info label="Status" value={progress.status} />
          <Info label="System runs" value={`${progress.completed_system_runs}/${progress.expected_system_runs}`} />
          <Info label="Turns" value={`${progress.completed_turns}/${progress.expected_turns}`} />
          <Info label="Measured metrics" value={progress.measured_metric_results} />
          <Info label="Pending metrics" value={progress.pending_metric_results} />
        </dl>
      ) : (
        <p className="text-sm text-slate-500">No experiment selected.</p>
      )}
      <button
        type="button"
        disabled={disabled}
        onClick={onStart}
        className="mt-4 inline-flex h-10 w-full items-center justify-center rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 disabled:opacity-60"
      >
        Start / Prepare Runs
      </button>
    </EvaluationPanel>
  );
}

function Info({ label, value }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value}</dd>
    </div>
  );
}
