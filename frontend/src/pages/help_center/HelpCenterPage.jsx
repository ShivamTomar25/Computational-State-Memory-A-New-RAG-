import { useState } from "react";
import { BookOpen, CheckCircle2 } from "lucide-react";
import {
  EmptyState,
  PageHero,
  PlatformShell,
  PrimaryButton,
  SecondaryButton,
  StatusBadge,
} from "../platform_shared/PlatformShell";
import { helpTopics } from "../platform_shared/platformService";

const onboardingCards = [
  "Patient Dashboard",
  "Upload Documents",
  "Chat",
  "Compare Systems",
  "CSM Viewer",
];

export function HelpCenterPage() {
  const gettingStarted = window.location.pathname.endsWith("/getting-started");
  const [query, setQuery] = useState("");
  const [dismissed, setDismissed] = useState([]);

  const topics = helpTopics.filter((topic) =>
    topic.toLowerCase().includes(query.trim().toLowerCase()),
  );

  function dismiss(topic) {
    setDismissed((current) => [...current, topic]);
  }

  return (
    <PlatformShell sectionLabel="Help">
      <PageHero
        eyebrow="Documentation and onboarding"
        title={gettingStarted ? "Getting Started" : "Help Center"}
        description="Find guidance for clinical workflows, evidence status, memory systems, exports, security, and privacy."
        actions={
          <PrimaryButton onClick={() => window.location.assign("/help/getting-started")}>
            <BookOpen className="h-4 w-4" aria-hidden="true" />
            Getting Started
          </PrimaryButton>
        }
      />

      <section className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <label className="block">
            <span className="mb-2 block text-sm font-medium text-slate-700">Search help topics</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search documentation..."
              className="h-11 w-full rounded-lg border border-slate-300 bg-white px-3.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-700 focus:ring-4 focus:ring-blue-100"
            />
          </label>
          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {topics.map((topic) => (
              <article key={topic} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-start gap-3">
                  <BookOpen className="mt-0.5 h-4 w-4 text-blue-700" aria-hidden="true" />
                  <div>
                    <h2 className="text-sm font-semibold text-slate-950">{topic}</h2>
                    <p className="mt-2 text-sm leading-6 text-slate-600">
                      Practical guidance for using this workflow with patient-scoped evidence and backend authorization.
                    </p>
                    <div className="mt-3">
                      <SecondaryButton>Open Topic</SecondaryButton>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
          {!topics.length ? (
            <div className="mt-5">
              <EmptyState title="No help topics found" text="Try another search term." />
            </div>
          ) : null}
        </section>

        <aside className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-base font-semibold text-slate-950">First-use onboarding</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Dismissible onboarding states for major workflows. These are kept in local UI state.
          </p>
          <div className="mt-4 space-y-3">
            {onboardingCards.map((card) => (
              <div key={card} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-950">{card}</p>
                    <div className="mt-2">
                      <StatusBadge label={dismissed.includes(card) ? "Complete" : "New"} />
                    </div>
                  </div>
                  {dismissed.includes(card) ? (
                    <CheckCircle2 className="h-5 w-5 text-green-700" aria-hidden="true" />
                  ) : (
                    <SecondaryButton onClick={() => dismiss(card)}>Dismiss</SecondaryButton>
                  )}
                </div>
              </div>
            ))}
          </div>
        </aside>
      </section>
    </PlatformShell>
  );
}
