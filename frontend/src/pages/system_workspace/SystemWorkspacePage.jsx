import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Database,
  Loader2,
  MessageSquareText,
  RefreshCcw,
  Search,
  ShieldCheck,
} from "lucide-react";

import { getPatient } from "../patient_shared/patientApi";
import {
  createSystemConversation,
  getMemorySystemStatistics,
  getSystemMessages,
  initializeMemorySystem,
  listIngestionRuns,
  listMemorySystems,
  listPatientMemorySystems,
  listSystemConversations,
  postSystemMessage,
  retrieveMemoryContext,
  syncMemorySystem,
} from "../../services/memorySystemsApi";

export function SystemWorkspacePage() {
  const { patientId, systemType } = getRouteParts();
  const [patient, setPatient] = useState(null);
  const [registryItem, setRegistryItem] = useState(null);
  const [patientSystem, setPatientSystem] = useState(null);
  const [statistics, setStatistics] = useState(null);
  const [runs, setRuns] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [selectedConversationId, setSelectedConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const [messageText, setMessageText] = useState("");
  const [retrieval, setRetrieval] = useState(null);
  const [lastGeneration, setLastGeneration] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [error, setError] = useState(null);

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === selectedConversationId),
    [conversations, selectedConversationId],
  );
  const systemInitialized = Boolean(patientSystem?.id);

  useEffect(() => {
    load();
  }, [patientId, systemType]);

  useEffect(() => {
    if (!selectedConversationId || !systemInitialized) {
      setMessages([]);
      return;
    }

    getSystemMessages(patientId, systemType, selectedConversationId)
      .then(setMessages)
      .catch((messageError) => setError(messageError.message));
  }, [patientId, systemType, selectedConversationId, systemInitialized]);

  async function load() {
    setLoading(true);
    setError(null);

    try {
      const [patientData, registryData, systemData] = await Promise.all([
        getPatient(patientId),
        listMemorySystems(),
        listPatientMemorySystems(patientId),
      ]);
      const item = registryData.find((system) => system.system_type === systemType);
      const instance = systemData.find((system) => system.system_type === systemType) ?? null;
      setPatient(patientData);
      setRegistryItem(item);
      setPatientSystem(instance);

      if (!instance?.id) {
        setStatistics(null);
        setRuns([]);
        setConversations([]);
        setSelectedConversationId(null);
        setMessages([]);
        return;
      }

      try {
        const [statsData, runData, conversationData] = await Promise.all([
          getMemorySystemStatistics(patientId, systemType),
          listIngestionRuns(patientId, systemType),
          listSystemConversations(patientId, systemType),
        ]);
        setStatistics(statsData);
        setRuns(runData);
        setConversations(conversationData);
        setSelectedConversationId((current) => current ?? conversationData[0]?.id ?? null);
      } catch (statsError) {
        setStatistics(null);
        setRuns([]);
        setConversations([]);
      }
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  async function runAction(label, action) {
    setActionLoading(label);
    setError(null);

    try {
      await action();
      await load();
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setActionLoading(null);
    }
  }

  async function inspectRetrieval(event) {
    event.preventDefault();

    if (!query.trim()) {
      return;
    }

    if (!systemInitialized) {
      setError("Initialize and sync this memory system before retrieving context.");
      return;
    }

    await runAction("retrieve", async () => {
      const result = await retrieveMemoryContext(patientId, systemType, {
        query: query.trim(),
        top_k: 8,
        token_budget: 6000,
        conversation_id: selectedConversationId,
        include_content: true,
        include_citations: true,
      });
      setRetrieval(result);
    });
  }

  async function createConversation() {
    if (!systemInitialized) {
      setError("Initialize this memory system before creating a conversation.");
      return;
    }

    await runAction("conversation", async () => {
      const conversation = await createSystemConversation(patientId, systemType, {
        title: `${registryItem?.display_name ?? "System"} conversation`,
      });
      setSelectedConversationId(conversation.id);
    });
  }

  async function sendMessage(event) {
    event.preventDefault();

    if (!messageText.trim()) {
      return;
    }

    if (!systemInitialized) {
      setError("Initialize and sync this memory system before sending a message.");
      return;
    }

    let conversationId = selectedConversationId;

    await runAction("message", async () => {
      if (!conversationId) {
        const conversation = await createSystemConversation(patientId, systemType, {
          title: `${registryItem?.display_name ?? "System"} conversation`,
        });
        conversationId = conversation.id;
        setSelectedConversationId(conversation.id);
      }

      const response = await postSystemMessage(patientId, systemType, conversationId, messageText.trim());
      setMessages((current) => {
        const nextMessages = [...current, response.message];

        if (response.assistant_message) {
          nextMessages.push(response.assistant_message);
        }

        return nextMessages;
      });
      setRetrieval(response.retrieval);
      setLastGeneration(response);
      setMessageText("");
    });
  }

  if (loading) {
    return <Shell patient={patient} patientId={patientId}>Loading system workspace...</Shell>;
  }

  return (
    <Shell patient={patient} patientId={patientId}>
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">
              {patient?.full_name ?? "Patient"} - {patient?.patient_code ?? patientId}
            </p>
            <h1 className="mt-2 text-2xl font-semibold text-slate-950">
              {registryItem?.display_name ?? formatType(systemType)}
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              {registryItem?.description ?? "Memory system workspace"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <ActionButton label="Initialize" loading={actionLoading === "initialize"} onClick={() => runAction("initialize", () => initializeMemorySystem(patientId, systemType))} />
            <ActionButton
              label="Sync"
              loading={actionLoading === "sync"}
              onClick={() =>
                runAction("sync", async () => {
                  if (!systemInitialized) {
                    await initializeMemorySystem(patientId, systemType);
                  }

                  await syncMemorySystem(patientId, systemType, {});
                })
              }
            />
            <ActionButton label="Refresh" loading={actionLoading === "refresh"} onClick={() => runAction("refresh", load)} />
          </div>
        </div>
      </section>

      {error ? <Notice message={error} /> : null}

      <section className="mt-6 grid gap-4 lg:grid-cols-4">
        <Metric label="Status" value={statistics?.status ?? "Not initialized"} />
        <Metric label="Patient sources" value={statistics?.source_counts?.patient_information ?? 0} />
        <Metric label="Document sources" value={statistics?.source_counts?.document ?? 0} />
        <Metric label="Private messages" value={statistics?.source_counts?.conversation ?? 0} />
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <Panel title="Retrieval Inspector" icon={<Search className="h-4 w-4" />}>
            <form onSubmit={inspectRetrieval} className="flex flex-col gap-3 sm:flex-row">
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Ask for context to retrieve"
                className="h-11 flex-1 rounded-lg border border-slate-300 px-3.5 text-sm outline-none focus:border-blue-700 focus:ring-4 focus:ring-blue-100"
              />
              <button
                type="submit"
                disabled={!systemInitialized || actionLoading === "retrieve"}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white disabled:opacity-60"
              >
                {actionLoading === "retrieve" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                Retrieve
              </button>
            </form>
            <p className="mt-3 text-sm text-slate-500">
              Retrieval is always system-scoped. Answers are generated only when the backend LLM provider is configured.
            </p>
            {retrieval ? <RetrievalResult retrieval={retrieval} /> : null}
          </Panel>

          <Panel title="Conversation" icon={<MessageSquareText className="h-4 w-4" />}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <select
                value={selectedConversationId ?? ""}
                onChange={(event) => setSelectedConversationId(event.target.value || null)}
                className="h-10 flex-1 rounded-lg border border-slate-300 px-3 text-sm"
              >
                <option value="">No conversation selected</option>
                {conversations.map((conversation) => (
                  <option key={conversation.id} value={conversation.id}>
                    {conversation.title || conversation.id}
                  </option>
                ))}
              </select>
              <ActionButton label="New Conversation" loading={actionLoading === "conversation"} disabled={!systemInitialized} onClick={createConversation} />
            </div>
            <div className="mt-4 max-h-80 space-y-3 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-4">
              {messages.map((message) => (
                <div key={message.id} className="rounded-lg bg-white p-3 text-sm">
                  <p className="font-semibold text-slate-950">{formatType(message.role)}</p>
                  <p className="mt-1 whitespace-pre-wrap text-slate-700">{message.content}</p>
                </div>
              ))}
              {!messages.length ? (
                <p className="text-sm text-slate-500">
                  {systemInitialized
                    ? "No messages in this system conversation."
                    : "Initialize this memory system before creating conversations."}
                </p>
              ) : null}
            </div>
            <form onSubmit={sendMessage} className="mt-4 flex flex-col gap-3 sm:flex-row">
              <input
                value={messageText}
                onChange={(event) => setMessageText(event.target.value)}
                placeholder="Send a system-specific message"
                className="h-11 flex-1 rounded-lg border border-slate-300 px-3.5 text-sm outline-none focus:border-blue-700 focus:ring-4 focus:ring-blue-100"
              />
              <button
                type="submit"
                disabled={!systemInitialized || actionLoading === "message"}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white disabled:opacity-60"
              >
                {actionLoading === "message" ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageSquareText className="h-4 w-4" />}
                Send
              </button>
            </form>
            {lastGeneration ? <GenerationResult result={lastGeneration} /> : null}
            {activeConversation ? (
              <p className="mt-3 text-xs text-slate-500">
                Conversation is isolated to {formatType(systemType)}.
              </p>
            ) : null}
          </Panel>
        </div>

        <aside className="space-y-6">
          <Panel title="Storage" icon={<Database className="h-4 w-4" />}>
            <dl className="space-y-3 text-sm">
              {Object.entries(statistics?.storage ?? {}).map(([key, value]) => (
                <InfoRow key={key} label={formatType(key)} value={typeof value === "object" ? JSON.stringify(value) : value} />
              ))}
              {!statistics?.storage ? <p className="text-sm text-slate-500">Initialize the system to view storage statistics.</p> : null}
            </dl>
          </Panel>

          <Panel title="Ingestion Runs" icon={<RefreshCcw className="h-4 w-4" />}>
            <div className="space-y-3">
              {runs.map((run) => (
                <div key={run.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <StatusBadge status={run.status} />
                    <span className="text-xs text-slate-500">{formatDateTime(run.created_at)}</span>
                  </div>
                  <p className="mt-2 text-slate-600">
                    {run.processed_count}/{run.source_count} sources processed
                  </p>
                </div>
              ))}
              {!runs.length ? <p className="text-sm text-slate-500">No ingestion runs yet.</p> : null}
            </div>
          </Panel>
        </aside>
      </section>
    </Shell>
  );
}

function GenerationResult({ result }) {
  const answer = result.answer;

  return (
    <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <StatusBadge status={result.generation_status} />
        <span className="text-xs text-slate-500">
          {result.model ? `${result.model} - prompt v${result.prompt_version}` : "No model call"}
        </span>
      </div>
      {answer ? (
        <div className="mt-3 space-y-3 text-sm">
          <p className="whitespace-pre-wrap text-slate-800">{answer.answer}</p>
          <dl className="grid gap-2 text-xs text-slate-500 sm:grid-cols-3">
            <InfoRow label="Uncertainty" value={formatType(answer.uncertainty)} />
            <InfoRow label="Insufficient evidence" value={answer.insufficient_evidence ? "Yes" : "No"} />
            <InfoRow label="Tokens" value={result.total_tokens} />
          </dl>
          {answer.citations?.length ? (
            <div className="flex flex-wrap gap-2">
              {answer.citations.map((citation) => (
                <span key={citation.citation_id} className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
                  {citation.citation_id}
                </span>
              ))}
            </div>
          ) : null}
          {answer.safety_note ? <p className="text-xs text-slate-500">{answer.safety_note}</p> : null}
        </div>
      ) : null}
      {result.warnings?.map((warning) => (
        <div key={warning} className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {warning}
        </div>
      ))}
    </div>
  );
}

function RetrievalResult({ retrieval }) {
  return (
    <div className="mt-5 space-y-3">
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        Generation status: {formatType(retrieval.generation_status)}
      </div>
      {retrieval.warnings.map((warning) => (
        <div key={warning} className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {warning}
        </div>
      ))}
      {retrieval.context_items.map((item) => (
        <div key={`${item.rank}-${item.system_native_id ?? item.canonical_source_id}`} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-semibold text-slate-950">Rank {item.rank}</p>
            <p className="text-xs text-slate-500">Score {item.score?.toFixed?.(4) ?? "n/a"}</p>
          </div>
          <p className="mt-2 text-sm text-slate-600">{item.content_preview}</p>
          <dl className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-3">
            <InfoRow label="Source" value={formatType(item.source_type)} />
            <InfoRow label="Subtype" value={formatType(item.source_subtype)} />
            <InfoRow label="Tokens" value={item.token_count} />
            <InfoRow label="Dense rank" value={item.dense_rank ?? "n/a"} />
            <InfoRow label="Lexical rank" value={item.lexical_rank ?? "n/a"} />
            <InfoRow label="Page" value={item.page_number ?? "n/a"} />
          </dl>
        </div>
      ))}
      {!retrieval.context_items.length ? <p className="text-sm text-slate-500">No context returned.</p> : null}
    </div>
  );
}

function Shell({ patient, patientId, children }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8">
          <button
            type="button"
            onClick={() => window.location.assign(`/patients/${patientId}`)}
            className="flex items-center gap-3 rounded-lg focus:outline-none focus:ring-4 focus:ring-blue-100"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-700 text-white">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="hidden text-left sm:block">
              <p className="text-sm font-semibold text-slate-950">Medical Memory Platform</p>
              <p className="text-xs text-slate-500">{patient?.full_name ?? "System workspace"}</p>
            </div>
          </button>
          <button
            type="button"
            onClick={() => window.location.assign(`/patients/${patientId}/compare`)}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Compare
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-5 py-8 sm:px-8">{children}</main>
    </div>
  );
}

function Panel({ title, icon, children }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-4">
        {icon}
        <h2 className="text-base font-semibold text-slate-950">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-semibold text-slate-950">{formatType(value)}</p>
    </div>
  );
}

function ActionButton({ label, loading, disabled = false, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading || disabled}
      className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
      {label}
    </button>
  );
}

function InfoRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="break-words text-right font-medium text-slate-800">{value || "Not set"}</dd>
    </div>
  );
}

function StatusBadge({ status }) {
  return (
    <span className="inline-flex rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
      {formatType(status)}
    </span>
  );
}

function Notice({ message }) {
  return (
    <div className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      {message}
    </div>
  );
}

function formatType(value = "") {
  if (!value) {
    return "Not set";
  }

  return String(value).replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatDateTime(value) {
  if (!value) {
    return "Not set";
  }

  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getRouteParts() {
  const segments = window.location.pathname.split("/").filter(Boolean);

  return {
    patientId: segments[1] || "",
    systemType: segments[3] || "",
  };
}
