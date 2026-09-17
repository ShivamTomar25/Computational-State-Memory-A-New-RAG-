import { useMemo, useState } from "react";
import { Archive, Bell, CheckCheck, Mail, MailOpen } from "lucide-react";
import {
  EmptyState,
  PageHero,
  PlatformShell,
  PrimaryButton,
  SecondaryButton,
  SelectField,
  StatePanel,
  StatusBadge,
  go,
} from "../platform_shared/PlatformShell";
import { notifications as notificationFixtures } from "../platform_shared/platformService";

const filterOptions = ["All", "Unread", "Clinical Review", "Processing", "Research", "Security"];

export function NotificationsCenterPage() {
  const [items, setItems] = useState(notificationFixtures);
  const [filter, setFilter] = useState("All");
  const [demoState, setDemoState] = useState("Ready");

  const visibleItems = useMemo(() => {
    const source = demoState === "Empty" ? [] : items;
    return source.filter((item) => {
      if (filter === "Unread") {
        return !item.read;
      }
      if (filter === "Clinical Review") {
        return ["Evidence Conflict", "Review Request", "Conversation Review"].includes(item.category);
      }
      if (filter === "Processing") {
        return ["Document Processing", "Memory Synchronization", "Failed Job"].includes(item.category);
      }
      if (filter === "Research") {
        return ["Experiment Complete", "Export Ready"].includes(item.category);
      }
      if (filter === "Security") {
        return item.category === "Security";
      }
      return true;
    });
  }, [items, filter, demoState]);

  function updateNotification(id, patch) {
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    );
  }

  function markAllRead() {
    setItems((current) => current.map((item) => ({ ...item, read: true })));
  }

  function archiveNotification(id) {
    setItems((current) => current.filter((item) => item.id !== id));
  }

  return (
    <PlatformShell sectionLabel="Notifications">
      <PageHero
        eyebrow="Operational and review events"
        title="Notifications"
        description="Review document processing, memory synchronization, evidence conflicts, research, export, and security notifications."
        actions={
          <PrimaryButton onClick={markAllRead}>
            <CheckCheck className="h-4 w-4" aria-hidden="true" />
            Mark All Read
          </PrimaryButton>
        }
      />

      <section className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField label="Filter" value={filter} onChange={setFilter} options={filterOptions} />
          <SelectField label="Demo state" value={demoState} onChange={setDemoState} options={["Ready", "Loading", "Empty", "Error", "Unauthorized"]} />
        </div>
      </section>

      {demoState === "Unauthorized" ? (
        <div className="mt-6">
          <StatePanel title="Access denied" text="Notifications are not available for this account." />
        </div>
      ) : null}
      {demoState === "Error" ? (
        <div className="mt-6">
          <StatePanel title="Notifications request failed" text="The notification list could not be loaded." />
        </div>
      ) : null}
      {demoState === "Loading" ? <NotificationSkeleton /> : null}
      {(demoState === "Empty" || (demoState === "Ready" && !visibleItems.length)) ? (
        <div className="mt-6">
          <EmptyState title="No notifications found" text="No notifications match the selected filter." />
        </div>
      ) : null}

      {demoState === "Ready" && visibleItems.length ? (
        <section className="mt-6 rounded-xl border border-slate-200 bg-white">
          <div className="divide-y divide-slate-200">
            {visibleItems.map((item) => (
              <article key={item.id} className={`${item.read ? "bg-white" : "bg-blue-50/50"} p-5`}>
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="flex gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
                      <Bell className="h-5 w-5" aria-hidden="true" />
                    </div>
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-slate-950">{item.title}</p>
                        <StatusBadge label={item.priority} />
                        {!item.read ? <StatusBadge label="New" /> : null}
                      </div>
                      <p className="mt-1 text-sm text-slate-600">{item.summary}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {item.category} - {item.timestamp}
                        {item.patient ? ` - ${item.patient}` : ""}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <SecondaryButton onClick={() => updateNotification(item.id, { read: !item.read })}>
                      {item.read ? <Mail className="h-4 w-4" aria-hidden="true" /> : <MailOpen className="h-4 w-4" aria-hidden="true" />}
                      {item.read ? "Mark Unread" : "Mark Read"}
                    </SecondaryButton>
                    <SecondaryButton onClick={() => archiveNotification(item.id)}>
                      <Archive className="h-4 w-4" aria-hidden="true" />
                      Archive
                    </SecondaryButton>
                    <SecondaryButton onClick={() => go(item.href)}>Open Related Item</SecondaryButton>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </PlatformShell>
  );
}

function NotificationSkeleton() {
  return (
    <div className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
      <div className="h-4 w-40 rounded bg-slate-200" />
      <div className="mt-4 h-5 w-2/3 rounded bg-slate-200" />
    </div>
  );
}
