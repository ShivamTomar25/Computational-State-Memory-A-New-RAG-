import { EvaluationPanel } from "./EvaluationPanel";

export function CorrectionRecoveryViewer({ recoveries = [] }) {
  return (
    <EvaluationPanel title="Correction Recovery">
      {recoveries.length ? <pre className="text-xs">{JSON.stringify(recoveries, null, 2)}</pre> : <p className="text-sm text-slate-500">Correction recovery results are pending measured runs.</p>}
    </EvaluationPanel>
  );
}
