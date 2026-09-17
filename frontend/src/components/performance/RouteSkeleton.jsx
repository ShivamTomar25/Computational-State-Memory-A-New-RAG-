export function RouteSkeleton({ label = "Loading page" }) {
  return (
    <div className="min-h-screen bg-slate-50 px-5 py-8 sm:px-8">
      <div className="mx-auto max-w-7xl space-y-5">
        <div className="h-16 rounded-xl border border-slate-200 bg-white" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <SkeletonBlock />
          <SkeletonBlock />
          <SkeletonBlock />
          <SkeletonBlock />
        </div>
        <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
          <div className="h-96 rounded-xl border border-slate-200 bg-white" />
          <div className="h-96 rounded-xl border border-slate-200 bg-white" />
        </div>
        <p className="text-sm text-slate-500">{label}</p>
      </div>
    </div>
  );
}

function SkeletonBlock() {
  return <div className="h-24 animate-pulse rounded-xl border border-slate-200 bg-white" />;
}
