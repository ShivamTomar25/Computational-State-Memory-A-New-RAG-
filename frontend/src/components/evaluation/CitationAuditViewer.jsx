import { EvaluationPanel } from "./EvaluationPanel";

export function CitationAuditViewer({ citations = [] }) {
  return (
    <EvaluationPanel title="Citation Audit">
      {citations.length ? <pre className="text-xs">{JSON.stringify(citations, null, 2)}</pre> : <p className="text-sm text-slate-500">Citation audit is pending measured outputs.</p>}
    </EvaluationPanel>
  );
}
