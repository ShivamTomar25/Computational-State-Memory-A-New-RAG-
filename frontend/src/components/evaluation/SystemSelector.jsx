import { EvaluationPanel } from "./EvaluationPanel";

const systems = ["long_context", "rolling_summary", "dense_rag", "hybrid_rag", "graph_rag", "hippo_rag", "csm"];

export function SystemSelector() {
  return (
    <EvaluationPanel title="System Readiness">
      <div className="grid gap-2">
        {systems.map((system) => (
          <div key={system} className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
            <span className="font-medium text-slate-800">{formatType(system)}</span>
            <span className="rounded-full border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-slate-600">Required</span>
          </div>
        ))}
      </div>
    </EvaluationPanel>
  );
}

function formatType(value) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
