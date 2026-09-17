import { EvaluationPanel } from "./EvaluationPanel";

export function MetricRankingTable({ rankings }) {
  const entries = Object.entries(rankings ?? {});

  return (
    <EvaluationPanel title="Per-Metric Rankings">
      <div className="space-y-3">
        {entries.map(([metric, ranking]) => (
          <div key={metric} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
            <div className="flex items-center justify-between gap-3">
              <p className="font-semibold text-slate-950">{formatType(metric)}</p>
              <span className="text-xs text-slate-500">{formatType(ranking.status)}</span>
            </div>
            {!ranking.rows.length ? <p className="mt-2 text-slate-500">No measured values yet.</p> : null}
          </div>
        ))}
      </div>
    </EvaluationPanel>
  );
}

function formatType(value) {
  return String(value).replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
