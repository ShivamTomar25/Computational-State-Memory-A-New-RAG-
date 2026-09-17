import { EvaluationPanel } from "./EvaluationPanel";

export function SystemComparisonTable({ results }) {
  return (
    <EvaluationPanel title="Metric Matrix">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">Metric</th>
              <th className="px-3 py-2">Value</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Reason</th>
            </tr>
          </thead>
          <tbody>
            {(results ?? []).map((result) => (
              <tr key={result.id} className="border-t border-slate-200">
                <td className="px-3 py-2 font-medium text-slate-900">{formatType(result.metric_name)}</td>
                <td className="px-3 py-2 text-slate-700">{result.value ?? "Not measured"}</td>
                <td className="px-3 py-2 text-slate-700">{result.applicable ? "Applicable" : "Pending"}</td>
                <td className="px-3 py-2 text-slate-500">{result.reason_not_applicable ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </EvaluationPanel>
  );
}

function formatType(value) {
  return String(value).replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}
