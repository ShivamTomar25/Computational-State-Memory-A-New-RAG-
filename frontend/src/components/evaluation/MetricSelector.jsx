import { EvaluationPanel } from "./EvaluationPanel";

export function MetricSelector({ metrics }) {
  return (
    <EvaluationPanel title="Metrics">
      <div className="max-h-80 space-y-2 overflow-auto">
        {metrics.map((metric) => (
          <div key={metric.metric_id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <p className="font-semibold text-slate-950">{metric.display_name}</p>
              <span className="text-xs text-slate-500">{formatDirection(metric.direction)}</span>
            </div>
            <p className="mt-1 text-slate-600">{metric.description}</p>
          </div>
        ))}
      </div>
    </EvaluationPanel>
  );
}

function formatDirection(value) {
  return value === "higher_is_better" ? "Higher better" : "Lower better";
}
