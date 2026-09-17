import { EvaluationPanel } from "./EvaluationPanel";

export function RetrievalTraceViewer({ traces = [] }) {
  return <AuditPanel title="Retrieval Traces" empty="Retrieval traces appear after live runs complete." items={traces} />;
}

function AuditPanel({ title, empty, items }) {
  return (
    <EvaluationPanel title={title}>
      {items.length ? <pre className="text-xs">{JSON.stringify(items, null, 2)}</pre> : <p className="text-sm text-slate-500">{empty}</p>}
    </EvaluationPanel>
  );
}
