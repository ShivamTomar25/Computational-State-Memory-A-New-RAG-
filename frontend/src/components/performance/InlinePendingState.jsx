import { Loader2 } from "lucide-react";

export function InlinePendingState({ label = "Working" }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-slate-500">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </span>
  );
}
