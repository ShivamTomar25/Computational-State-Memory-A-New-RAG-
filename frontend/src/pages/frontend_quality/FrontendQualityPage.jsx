import {
  PageHero,
  PlatformShell,
  StatusBadge,
} from "../platform_shared/PlatformShell";

const qualityGroups = [
  {
    title: "Navigation",
    items: ["Application header", "Patient workspace navigation", "Admin navigation", "Breadcrumbs", "Mobile navigation", "Keyboard navigation"],
  },
  {
    title: "Responsive Design",
    items: ["Desktop", "Tablet", "Mobile", "Narrow mobile", "Large monitors", "Intentional table scrolling"],
  },
  {
    title: "Accessibility",
    items: ["Semantic landmarks", "Heading hierarchy", "Form labels", "Visible focus states", "Screen-reader status text", "Table captions", "Button names", "Contrast"],
  },
  {
    title: "Loading, Empty, Error",
    items: ["Initial loading", "Action loading", "True empty states", "Filtered empty states", "Authorization failure", "Network failure", "Version conflict"],
  },
  {
    title: "Medical Safety",
    items: ["Evidence versus generated answers", "Evidence versus computational states", "Insufficient evidence", "Conflicting evidence", "Citation availability", "Synthetic fixture labelling"],
  },
  {
    title: "Security",
    items: ["No sensitive localStorage", "No tokens in URLs", "No patient analytics payloads", "Safe content rendering", "Permission-aware controls", "Backend as authorization source"],
  },
];

export function FrontendQualityPage() {
  return (
    <PlatformShell sectionLabel="Frontend quality">
      <PageHero
        eyebrow="Final quality pass"
        title="Frontend Quality Checklist"
        description="Review platform-wide navigation, responsive behavior, accessibility, error states, medical safety language, performance, and security requirements."
      />

      <section className="mt-6 grid gap-6 lg:grid-cols-2">
        {qualityGroups.map((group) => (
          <article key={group.title} className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-base font-semibold text-slate-950">{group.title}</h2>
              <StatusBadge label="Ready" />
            </div>
            <div className="mt-4 grid gap-2">
              {group.items.map((item) => (
                <div key={item} className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                  <span className="text-sm text-slate-700">{item}</span>
                  <StatusBadge label="Complete" />
                </div>
              ))}
            </div>
          </article>
        ))}
      </section>

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="text-base font-semibold text-slate-950">Known build context</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          This project is JavaScript-only and currently has no configured test,
          lint, or TypeScript scripts. The UI exposes boundary states for
          backend integration.
        </p>
      </section>
    </PlatformShell>
  );
}
