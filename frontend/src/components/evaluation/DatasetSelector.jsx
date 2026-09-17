import { EvaluationPanel } from "./EvaluationPanel";

export function DatasetSelector({ datasets, selectedDatasetId, onChange }) {
  return (
    <EvaluationPanel title="Dataset">
      <select
        value={selectedDatasetId ?? ""}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-800 outline-none focus:border-blue-700 focus:ring-4 focus:ring-blue-100"
      >
        <option value="">Select dataset</option>
        {datasets.map((dataset) => (
          <option key={dataset.id} value={dataset.id}>
            {dataset.name} v{dataset.version} - {dataset.split}
          </option>
        ))}
      </select>
      <dl className="mt-4 space-y-2 text-sm">
        {datasets
          .filter((dataset) => dataset.id === selectedDatasetId)
          .map((dataset) => (
            <div key={dataset.id}>
              <Info label="Cases" value={dataset.case_count} />
              <Info label="Status" value={dataset.status} />
              <Info label="Checksum" value={dataset.checksum.slice(0, 16)} />
            </div>
          ))}
      </dl>
    </EvaluationPanel>
  );
}

function Info({ label, value }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-right font-medium text-slate-800">{value}</dd>
    </div>
  );
}
