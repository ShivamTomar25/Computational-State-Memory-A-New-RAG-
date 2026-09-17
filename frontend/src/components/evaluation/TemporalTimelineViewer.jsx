import { EvaluationPanel } from "./EvaluationPanel";

export function TemporalTimelineViewer({ events = [] }) {
  return (
    <EvaluationPanel title="Temporal Timeline">
      {events.length ? <pre className="text-xs">{JSON.stringify(events, null, 2)}</pre> : <p className="text-sm text-slate-500">Timeline diagnostics are pending live experiment turns.</p>}
    </EvaluationPanel>
  );
}
