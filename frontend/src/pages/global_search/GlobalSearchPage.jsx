import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import {
  EmptyState,
  PageHero,
  PlatformShell,
  SecondaryButton,
  SelectField,
  StatePanel,
  StatusBadge,
  go,
  inputClass,
} from "../platform_shared/PlatformShell";
import { searchResults } from "../platform_shared/platformService";

const filters = ["All", "Patients", "Documents", "Evidence", "Conversations", "States", "Experiments"];

export function GlobalSearchPage() {
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [filter, setFilter] = useState("All");
  const [demoState, setDemoState] = useState("Ready");

  useEffect(() => {
    function handleShortcut(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        document.getElementById("global-search-input")?.focus();
      }
    }

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(query), 220);
    return () => window.clearTimeout(timer);
  }, [query]);

  const results = useMemo(() => {
    const text = debouncedQuery.trim().toLowerCase();
    const source = demoState === "Empty" ? [] : searchResults;

    return source.filter((result) => {
      const matchesType = filter === "All" || result.type === filter;
      const matchesText =
        !text ||
        `${result.title} ${result.summary} ${result.type}`.toLowerCase().includes(text);
      return matchesType && matchesText;
    });
  }, [debouncedQuery, filter, demoState]);

  const grouped = filters
    .filter((item) => item !== "All")
    .map((type) => ({
      type,
      items: results.filter((result) => result.type === type),
    }))
    .filter((group) => group.items.length);

  return (
    <PlatformShell sectionLabel="Global search">
      <PageHero
        eyebrow="Authorized platform search"
        title="Global Search"
        description="Search patients, documents, evidence, conversations, computational states, experiments, and authorized audit events."
      />

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_180px_180px]">
          <label className="relative block">
            <span className="mb-2 block text-sm font-medium text-slate-700">Search</span>
            <Search className="pointer-events-none absolute left-3 top-[42px] h-4 w-4 text-slate-400" aria-hidden="true" />
            <input
              id="global-search-input"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search patients, documents, evidence, conversations, and states..."
              className={inputClass("pl-9")}
            />
          </label>
          <SelectField label="Filter" value={filter} onChange={setFilter} options={filters} />
          <SelectField label="Demo state" value={demoState} onChange={setDemoState} options={["Ready", "Loading", "Empty", "Error", "Unauthorized"]} />
        </div>
        <p className="mt-3 text-xs text-slate-500">
          Shortcut: Command + K or Control + K. Unauthorized records are not shown.
        </p>
      </section>

      {demoState === "Unauthorized" ? (
        <div className="mt-6">
          <StatePanel title="Access denied" text="This account is not authorized to use global search." />
        </div>
      ) : null}

      {demoState === "Error" ? (
        <div className="mt-6">
          <StatePanel title="Search failed" text="The search service could not complete the request." />
        </div>
      ) : null}

      {demoState === "Loading" ? <SearchSkeleton /> : null}

      {(demoState === "Empty" || (demoState === "Ready" && !results.length)) ? (
        <div className="mt-6">
          <EmptyState
            title="No results found"
            text="No authorized resources match this search."
          />
        </div>
      ) : null}

      {demoState === "Ready" && results.length ? (
        <section className="mt-6 space-y-6">
          {grouped.map((group) => (
            <section key={group.type} className="rounded-xl border border-slate-200 bg-white p-5">
              <h2 className="text-base font-semibold text-slate-950">{group.type}</h2>
              <div className="mt-4 divide-y divide-slate-200">
                {group.items.map((item) => (
                  <article key={item.id} className="flex flex-col gap-3 py-4 lg:flex-row lg:items-center lg:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold text-slate-950">{item.title}</h3>
                        <StatusBadge label={item.status} />
                      </div>
                      <p className="mt-1 text-sm text-slate-600">{item.summary}</p>
                      <p className="mt-1 text-xs text-slate-500">{item.timestamp}</p>
                    </div>
                    <SecondaryButton onClick={() => go(item.href)}>Open</SecondaryButton>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </section>
      ) : null}
    </PlatformShell>
  );
}

function SearchSkeleton() {
  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
      <div className="h-4 w-40 rounded bg-slate-200" />
      <div className="mt-4 h-5 w-2/3 rounded bg-slate-200" />
    </div>
  );
}
