import { EvaluationPanel } from "./EvaluationPanel";

export function HallucinationViewer({ hallucinations = [] }) {
  return (
    <EvaluationPanel title="Hallucination Audit">
      {hallucinations.length ? <pre className="text-xs">{JSON.stringify(hallucinations, null, 2)}</pre> : <p className="text-sm text-slate-500">No measured hallucination classifications yet.</p>}
    </EvaluationPanel>
  );
}
