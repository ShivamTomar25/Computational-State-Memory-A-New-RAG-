import { EvaluationPanel } from "./EvaluationPanel";

export function ContradictionViewer({ contradictions = [] }) {
  return (
    <EvaluationPanel title="Contradiction Handling">
      {contradictions.length ? <pre className="text-xs">{JSON.stringify(contradictions, null, 2)}</pre> : <p className="text-sm text-slate-500">Contradiction evaluations are pending measured runs.</p>}
    </EvaluationPanel>
  );
}
