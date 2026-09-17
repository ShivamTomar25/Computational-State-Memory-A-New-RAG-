import {
  PageHero,
  PlatformShell,
  PrimaryButton,
  SecondaryButton,
  go,
} from "../platform_shared/PlatformShell";

const errorMessages = {
  "400": ["Bad Request", "The request could not be understood. Check the route or submitted values."],
  "401": ["Session Expired", "Your session has expired. Sign in again to continue."],
  "403": ["Access Denied", "You do not have permission to view this resource."],
  "404": ["Page Not Found", "The page does not exist or has moved."],
  "409": ["Version Conflict", "Patient information changed while this page was open."],
  "422": ["Invalid Data", "Some submitted values are invalid."],
  "429": ["Too Many Requests", "Too many requests were sent. Wait before retrying."],
  "500": ["Unexpected Error", "Something went wrong. Internal stack traces are not displayed."],
  "503": ["Service Unavailable", "A required service is temporarily unavailable."],
  offline: ["Offline", "The network appears unavailable. Check your connection and retry."],
};

export function ErrorPage({ code: providedCode }) {
  const pathCode = window.location.pathname.split("/").filter(Boolean).pop();
  const code = providedCode || pathCode || "404";
  const [title, text] = errorMessages[code] || errorMessages["404"];
  const traceId = `trace-ui-${code}-20260717`;

  return (
    <PlatformShell sectionLabel="Error state">
      <PageHero
        eyebrow={`Error ${code}`}
        title={title}
        description={text}
        actions={
          <>
            <PrimaryButton onClick={() => (code === "401" ? go("/") : window.location.reload())}>
              {code === "401" ? "Sign In" : "Refresh"}
            </PrimaryButton>
            <SecondaryButton onClick={() => go("/patients")}>Back to Patients</SecondaryButton>
          </>
        }
      >
        <p className="mt-3 text-sm text-slate-500">Support trace ID: {traceId}</p>
      </PageHero>

      {code === "409" ? (
        <section className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-5">
          <h2 className="text-base font-semibold text-amber-900">Patient information changed</h2>
          <p className="mt-2 text-sm leading-6 text-amber-800">
            This page may be using an older patient memory version.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <PrimaryButton onClick={() => window.location.reload()}>Refresh</PrimaryButton>
            <SecondaryButton onClick={() => go("/patients/1/timeline")}>Review Changes</SecondaryButton>
            <SecondaryButton onClick={() => go("/patients/1")}>Cancel Current Action</SecondaryButton>
          </div>
        </section>
      ) : null}

      <section className="mt-6 grid gap-4 md:grid-cols-2">
        {["Query error fallback", "Lazy-load failure fallback", "Permission boundary", "Feature-disabled boundary"].map((boundary) => (
          <article key={boundary} className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-base font-semibold text-slate-950">{boundary}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Boundary state prepared with safe messaging and no internal error payloads.
            </p>
          </article>
        ))}
      </section>
    </PlatformShell>
  );
}
