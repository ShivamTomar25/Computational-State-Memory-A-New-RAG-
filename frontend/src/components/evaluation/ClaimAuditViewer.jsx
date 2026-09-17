import { EvaluationPanel } from "./EvaluationPanel";

export function ClaimAuditViewer({ claims = [] }) {
  return (
    <EvaluationPanel title="Claim Audit">
      {claims.length ? <pre className="text-xs">{JSON.stringify(claims, null, 2)}</pre> : <p className="text-sm text-slate-500">Claim classifications are pending measured outputs.</p>}
    </EvaluationPanel>
  );
}
