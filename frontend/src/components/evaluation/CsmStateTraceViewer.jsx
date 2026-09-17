import { EvaluationPanel } from "./EvaluationPanel";

export function CsmStateTraceViewer({ traces = [] }) {
  return (
    <EvaluationPanel title="CSM State Trace">
      {traces.length ? <pre className="text-xs">{JSON.stringify(traces, null, 2)}</pre> : <p className="text-sm text-slate-500">CSM trace diagnostics are pending measured runs.</p>}
    </EvaluationPanel>
  );
}
