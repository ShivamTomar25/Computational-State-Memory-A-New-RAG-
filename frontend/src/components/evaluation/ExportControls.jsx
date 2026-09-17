import { EvaluationPanel } from "./EvaluationPanel";

const exportTypes = ["json", "csv", "markdown", "latex"];

export function ExportControls({ disabled, onExport }) {
  return (
    <EvaluationPanel title="Exports">
      <div className="flex flex-wrap gap-2">
        {exportTypes.map((type) => (
          <button
            key={type}
            type="button"
            disabled={disabled}
            onClick={() => onExport(type)}
            className="inline-flex h-10 items-center rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 disabled:opacity-60"
          >
            {type.toUpperCase()}
          </button>
        ))}
      </div>
    </EvaluationPanel>
  );
}
