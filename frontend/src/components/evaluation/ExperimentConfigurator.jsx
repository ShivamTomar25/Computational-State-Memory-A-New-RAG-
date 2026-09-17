import { EvaluationPanel } from "./EvaluationPanel";

export function ExperimentConfigurator({ disabled, onCreate }) {
  return (
    <EvaluationPanel title="Experiment Configuration">
      <button
        type="button"
        disabled={disabled}
        onClick={onCreate}
        className="inline-flex h-11 w-full items-center justify-center rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white disabled:opacity-60"
      >
        Create Smoke Experiment
      </button>
      <p className="mt-3 text-sm leading-6 text-slate-500">
        Full and pilot runs require explicit cost confirmation and are not started automatically.
      </p>
    </EvaluationPanel>
  );
}
