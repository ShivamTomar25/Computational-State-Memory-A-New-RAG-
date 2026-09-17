export function ConfidenceInterval({ value }) {
  if (!value) {
    return <span className="text-slate-500">CI pending</span>;
  }

  return <span>{value.lower} to {value.upper}</span>;
}
