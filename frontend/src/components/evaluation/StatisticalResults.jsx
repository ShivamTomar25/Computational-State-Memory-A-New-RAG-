import { EvaluationPanel } from "./EvaluationPanel";

export function StatisticalResults({ statistics = [] }) {
  return (
    <EvaluationPanel title="Statistical Results">
      {statistics.length ? <pre className="text-xs">{JSON.stringify(statistics, null, 2)}</pre> : <p className="text-sm text-slate-500">Paired statistics require measured case-level scores.</p>}
    </EvaluationPanel>
  );
}
