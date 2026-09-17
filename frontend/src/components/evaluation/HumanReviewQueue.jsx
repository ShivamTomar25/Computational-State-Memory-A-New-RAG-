import { EvaluationPanel } from "./EvaluationPanel";

export function HumanReviewQueue({ items = [] }) {
  return (
    <EvaluationPanel title="Human Review Queue">
      {items.length ? <pre className="text-xs">{JSON.stringify(items, null, 2)}</pre> : <p className="text-sm text-slate-500">No unresolved blinded review items.</p>}
    </EvaluationPanel>
  );
}
