import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  Database,
  FileText,
  Loader2,
  MessageSquareText,
  Plus,
  RefreshCcw,
  Send,
  ShieldCheck,
} from "lucide-react";

import { getPatient } from "../patient_shared/patientApi";
import {
  createSystemConversation,
  getMemorySystemStatistics,
  getSystemMessages,
  initializeMemorySystem,
  listMemorySystems,
  listPatientMemorySystems,
  listSystemConversations,
  postSystemMessage,
  syncMemorySystem,
} from "../../services/memorySystemsApi";
import { cacheCsmMessages, syncCsm } from "../computational_state_memory/csmService";

export function ConversationHistoryPage() {
  const patientId = getPatientId();
  const routeConversationId = getConversationId();
  const [patient, setPatient] = useState(null);
  const [registry, setRegistry] = useState([]);
  const [patientSystems, setPatientSystems] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [selectedSystemId, setSelectedSystemId] = useState("dense_rag");
  const [selectedConversationId, setSelectedConversationId] = useState(routeConversationId);
  const [messages, setMessages] = useState([]);
  const [messageText, setMessageText] = useState("");
  const [lastGeneration, setLastGeneration] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingSystem, setLoadingSystem] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [action, setAction] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const systems = useMemo(() => {
    return registry.map((item) => ({
      ...item,
      instance: patientSystems.find((system) => system.system_type === item.system_type),
    }));
  }, [registry, patientSystems]);

  const selectedSystem = systems.find((system) => system.system_type === selectedSystemId);
  const selectedSystemInitialized = Boolean(selectedSystem?.instance?.id);
  const activeConversation = conversations.find(
    (conversation) => conversation.id === selectedConversationId,
  );

  useEffect(() => {
    loadBase();
  }, [patientId]);

  useEffect(() => {
    if (!registry.length) {
      return;
    }

    if (!registry.some((item) => item.system_type === selectedSystemId)) {
      setSelectedSystemId(registry[0].system_type);
    }
  }, [registry, selectedSystemId]);

  useEffect(() => {
    if (!selectedSystemId) {
      return;
    }

    loadSystemData(selectedSystemId, routeConversationId);
  }, [patientId, selectedSystemId, patientSystems]);

  useEffect(() => {
    if (!selectedConversationId || !selectedSystemId || !selectedSystemInitialized) {
      setMessages([]);
      return;
    }

    loadMessages(selectedSystemId, selectedConversationId);
  }, [patientId, selectedSystemId, selectedConversationId, selectedSystemInitialized]);

  async function loadBase() {
    setLoading(true);
    setError(null);

    try {
      const [patientData, registryData, systemData] = await Promise.all([
        getPatient(patientId),
        listMemorySystems(),
        listPatientMemorySystems(patientId),
      ]);
      setPatient(patientData);
      setRegistry(registryData);
      setPatientSystems(systemData);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }

  async function loadSystemData(systemType, preferredConversationId = null) {
    setLoadingSystem(true);
    setError(null);
    setLastGeneration(null);

    const instance = patientSystems.find((system) => system.system_type === systemType);

    if (!instance?.id) {
      setStatistics(null);
      setConversations([]);
      setMessages([]);
      updateSelectedConversation(null);
      setLoadingSystem(false);
      return;
    }

    try {
      const [statsData, conversationData] = await Promise.all([
        getMemorySystemStatistics(patientId, systemType),
        listSystemConversations(patientId, systemType),
      ]);
      setStatistics(statsData);
      setConversations(conversationData);

      const nextConversationId =
        preferredConversationId && conversationData.some((conversation) => conversation.id === preferredConversationId)
          ? preferredConversationId
          : conversationData[0]?.id ?? null;

      updateSelectedConversation(nextConversationId);
    } catch (systemError) {
      setStatistics(null);
      setConversations([]);
      setMessages([]);
      updateSelectedConversation(null);
      setError(systemError.message);
    } finally {
      setLoadingSystem(false);
    }
  }

  async function loadMessages(systemType, conversationId) {
    setLoadingMessages(true);
    setError(null);

    try {
      const messageData = await getSystemMessages(patientId, systemType, conversationId);
      setMessages(messageData);
    } catch (messageError) {
      setError(messageError.message);
    } finally {
      setLoadingMessages(false);
    }
  }

  function updateSelectedConversation(conversationId) {
    setSelectedConversationId(conversationId);

    const nextPath = conversationId
      ? `/patients/${patientId}/chat/${conversationId}`
      : `/patients/${patientId}/chat`;

    if (window.location.pathname !== nextPath) {
      window.history.replaceState({}, "", nextPath);
    }
  }

  async function runAction(label, handler) {
    setAction(label);
    setError(null);
    setSuccess(null);

    try {
      await handler();
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setAction(null);
    }
  }

  async function initializeSelectedSystem() {
    if (!selectedSystemId) {
      return;
    }

    await runAction("initialize", async () => {
      await initializeMemorySystem(patientId, selectedSystemId);
      setSuccess(`${formatType(selectedSystemId)} initialized.`);
      const systemData = await listPatientMemorySystems(patientId);
      setPatientSystems(systemData);
    });
  }

  async function syncSelectedSystem() {
    if (!selectedSystemId) {
      return;
    }

    await runAction("sync", async () => {
      if (!selectedSystemInitialized) {
        await initializeMemorySystem(patientId, selectedSystemId);
      }

      await syncMemorySystem(patientId, selectedSystemId, {
        include_patient_information: true,
        include_documents: true,
        include_conversation: true,
      });
      setSuccess(`${formatType(selectedSystemId)} synchronized.`);
      const systemData = await listPatientMemorySystems(patientId);
      setPatientSystems(systemData);
    });
  }

  async function refreshSelectedSystem() {
    if (!selectedSystemId) {
      return;
    }

    await runAction("refresh", async () => {
      const [patientData, registryData, systemData] = await Promise.all([
        getPatient(patientId),
        listMemorySystems(),
        listPatientMemorySystems(patientId),
      ]);
      setPatient(patientData);
      setRegistry(registryData);
      setPatientSystems(systemData);
    });
  }

  async function ensureSelectedSystemReady() {
    if (!selectedSystemId) {
      throw new Error("Select a memory system before starting chat.");
    }

    let instance = patientSystems.find((system) => system.system_type === selectedSystemId);

    if (!instance?.id) {
      await initializeMemorySystem(patientId, selectedSystemId);
      const initializedSystems = await listPatientMemorySystems(patientId);
      setPatientSystems(initializedSystems);
      instance = initializedSystems.find((system) => system.system_type === selectedSystemId);
    }

    if (!instance?.last_synced_at || instance.status !== "ready") {
      await syncMemorySystem(patientId, selectedSystemId, {
        include_patient_information: true,
        include_documents: true,
        include_conversation: true,
      });
      const syncedSystems = await listPatientMemorySystems(patientId);
      setPatientSystems(syncedSystems);
    }
  }

  async function createConversation() {
    if (!selectedSystemId) {
      return null;
    }

    let createdConversation = null;

    await runAction("conversation", async () => {
      await ensureSelectedSystemReady();
      createdConversation = await createSystemConversation(patientId, selectedSystemId, {
        title: `${selectedSystem?.display_name ?? formatType(selectedSystemId)} conversation`,
      });
      setConversations((current) => [createdConversation, ...current]);
      updateSelectedConversation(createdConversation.id);
      setMessages([]);
    });

    return createdConversation;
  }

  async function sendMessage(event) {
    event.preventDefault();

    const content = messageText.trim();

    if (!content || !selectedSystemId || action === "message") {
      return;
    }

    setAction("message");
    setError(null);
    setSuccess(null);

    try {
      await ensureSelectedSystemReady();

      let conversationId = selectedConversationId;

      if (!conversationId) {
        const createdConversation = await createSystemConversation(patientId, selectedSystemId, {
          title: `${selectedSystem?.display_name ?? formatType(selectedSystemId)} conversation`,
        });
        conversationId = createdConversation.id;
        setConversations((current) => [createdConversation, ...current]);
        updateSelectedConversation(createdConversation.id);
      }

      const response = await postSystemMessage(patientId, selectedSystemId, conversationId, content);
      const nextMessages = [response.message];

      if (response.assistant_message) {
        nextMessages.push(response.assistant_message);
      }

      setMessages((current) => [...current, ...nextMessages]);
      cacheCsmMessages(patientId, selectedSystemId, conversationId, nextMessages);
      syncCsm(patientId).catch(() => {});
      setLastGeneration(response);
      setMessageText("");
      const conversationData = await listSystemConversations(patientId, selectedSystemId);
      setConversations(conversationData);
    } catch (sendError) {
      setError(sendError.message);
    } finally {
      setAction(null);
    }
  }

  if (loading) {
    return <PageShell patient={patient} patientId={patientId}>Loading patient chat...</PageShell>;
  }

  return (
    <PageShell patient={patient} patientId={patientId}>
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-clinical sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-medium text-slate-500">
              {patient?.full_name ?? "Patient"} - {patient?.patient_code ?? patientId}
            </p>
            <h1 className="mt-2 text-2xl font-semibold text-slate-950">Patient Chat</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Ask patient-specific questions through the selected memory system. Messages, retrieval context, and LLM answers are stored by the backend.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <ActionButton label="Initialize" loading={action === "initialize"} onClick={initializeSelectedSystem} />
            <ActionButton label="Sync" loading={action === "sync"} onClick={syncSelectedSystem} />
            <ActionButton label="Refresh" loading={action === "refresh"} onClick={refreshSelectedSystem} />
          </div>
        </div>
      </section>

      {error ? <Notice tone="error" message={error} /> : null}
      {success ? <Notice tone="success" message={success} /> : null}

      <section className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="System status" value={statistics?.status ?? selectedSystem?.instance?.status ?? "Not initialized"} />
        <Metric label="Patient sources" value={statistics?.source_counts?.patient_information ?? 0} />
        <Metric label="Document sources" value={statistics?.source_counts?.document ?? 0} />
        <Metric label="Conversation sources" value={statistics?.source_counts?.conversation ?? 0} />
      </section>

      <section className="mt-6 grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)_360px]">
        <aside className="space-y-6">
          <Panel title="Memory System" icon={<Database className="h-4 w-4" />}>
            <label className="text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="memory-system">
              Active system
            </label>
            <select
              id="memory-system"
              value={selectedSystemId}
              onChange={(event) => {
                setSelectedSystemId(event.target.value);
                updateSelectedConversation(null);
              }}
              className="mt-2 h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-800 outline-none focus:border-blue-700 focus:ring-4 focus:ring-blue-100"
            >
              {systems.map((system) => (
                <option key={system.system_type} value={system.system_type}>
                  {system.display_name ?? formatType(system.system_type)}
                </option>
              ))}
            </select>
            <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
              <StatusBadge status={selectedSystem?.instance?.status ?? "not_initialized"} />
              <p className="mt-3 text-slate-600">
                {selectedSystem?.description ?? "Select a memory system for this patient."}
              </p>
            </div>
          </Panel>

          <Panel title="Conversations" icon={<MessageSquareText className="h-4 w-4" />}>
            <button
              type="button"
              onClick={createConversation}
              disabled={action === "conversation" || action === "message"}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-blue-700 px-3 text-sm font-semibold text-white disabled:opacity-60"
            >
              {action === "conversation" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              New Conversation
            </button>
            <div className="mt-4 max-h-[420px] space-y-2 overflow-auto">
              {loadingSystem ? <LoadingLine label="Loading conversations" /> : null}
              {conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  type="button"
                  onClick={() => updateSelectedConversation(conversation.id)}
                  className={`w-full rounded-lg border px-3 py-3 text-left text-sm transition ${
                    conversation.id === selectedConversationId
                      ? "border-blue-300 bg-blue-50 text-blue-900"
                      : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  <span className="block font-semibold">{conversation.title || "Untitled conversation"}</span>
                  <span className="mt-1 block text-xs text-slate-500">
                    {formatDateTime(conversation.last_message_at ?? conversation.updated_at)}
                  </span>
                </button>
              ))}
              {!loadingSystem && !conversations.length ? (
                <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">
                  {selectedSystemInitialized
                    ? "No conversations for this system yet."
                    : "Start a conversation or send a question. The selected system will initialize automatically."}
                </p>
              ) : null}
            </div>
          </Panel>
        </aside>

        <Panel title={activeConversation?.title || "Conversation"} icon={<MessageSquareText className="h-4 w-4" />}>
          <div className="flex min-h-[520px] flex-col">
            <div className="flex-1 space-y-3 overflow-auto rounded-lg border border-slate-200 bg-slate-50 p-4">
              {loadingMessages ? <LoadingLine label="Loading messages" /> : null}
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {!loadingMessages && !messages.length ? (
                <div className="flex h-full min-h-[360px] flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white px-6 text-center">
                  <MessageSquareText className="h-8 w-8 text-slate-400" />
                  <p className="mt-3 text-sm font-semibold text-slate-800">No messages yet</p>
                  <p className="mt-1 max-w-sm text-sm leading-6 text-slate-500">
                    {selectedSystemInitialized
                      ? "Create a conversation or send a question to start a backend-backed patient chat."
                      : "Send a question to initialize, sync, and start patient chat."}
                  </p>
                </div>
              ) : null}
            </div>
            <form onSubmit={sendMessage} className="mt-4 flex flex-col gap-3 sm:flex-row">
              <input
                value={messageText}
                onChange={(event) => setMessageText(event.target.value)}
                placeholder="Ask a patient-specific question"
                className="h-11 flex-1 rounded-lg border border-slate-300 px-3.5 text-sm outline-none focus:border-blue-700 focus:ring-4 focus:ring-blue-100"
              />
              <button
                type="submit"
                disabled={!messageText.trim() || action === "message" || action === "conversation"}
                className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-blue-700 px-5 text-sm font-semibold text-white disabled:opacity-60"
              >
                {action === "message" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                {action === "message" ? "Sending" : "Send"}
              </button>
            </form>
          </div>
        </Panel>

        <aside className="space-y-6">
          <Panel title="Latest Result" icon={<FileText className="h-4 w-4" />}>
            {lastGeneration ? (
              <GenerationResult result={lastGeneration} />
            ) : (
              <p className="text-sm leading-6 text-slate-500">
                Send a question to see retrieval count, LLM status, answer metadata, and warnings.
              </p>
            )}
          </Panel>

          <Panel title="Storage" icon={<Database className="h-4 w-4" />}>
            {statistics?.storage ? (
              <dl className="space-y-3 text-sm">
                {Object.entries(statistics.storage).map(([key, value]) => (
                  <InfoRow key={key} label={formatType(key)} value={formatStorageValue(value)} />
                ))}
              </dl>
            ) : (
              <p className="text-sm leading-6 text-slate-500">
                Initialize and sync this system to view storage details.
              </p>
            )}
          </Panel>
        </aside>
      </section>
    </PageShell>
  );
}

function PageShell({ patient, patientId, children }) {
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
              <p className="text-xs text-slate-500">{patient?.full_name ?? "Patient chat"}</p>
            </div>
          </button>
          <button
            type="button"
            onClick={() => window.location.assign(`/patients/${patientId}`)}
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Patient
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

function ActionButton({ label, loading, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
      {label}
    </button>
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

function MessageBubble({ message }) {
  const isUser = message.role === "user" || message.role === "doctor";

  return (
    <article className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[88%] rounded-lg border px-4 py-3 text-sm ${
          isUser
            ? "border-blue-200 bg-blue-700 text-white"
            : "border-slate-200 bg-white text-slate-800"
        }`}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className={`font-semibold ${isUser ? "text-white" : "text-slate-950"}`}>
            {formatType(message.role)}
          </p>
          <span className={isUser ? "text-xs text-blue-100" : "text-xs text-slate-500"}>
            {formatDateTime(message.event_time ?? message.created_at)}
          </span>
        </div>
        <p className="mt-2 whitespace-pre-wrap leading-6">{message.content}</p>
        <div className={`mt-3 text-xs ${isUser ? "text-blue-100" : "text-slate-500"}`}>
          Status: {formatType(message.generation_status)}
          {message.token_count ? ` - ${message.token_count} tokens` : ""}
        </div>
      </div>
    </article>
  );
}

function GenerationResult({ result }) {
  const retrieval = result.retrieval;
  const answer = result.answer;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <StatusBadge status={result.generation_status} />
          <span className="text-xs text-slate-500">
            {result.model ? `${result.model} - prompt v${result.prompt_version}` : "No LLM model call"}
          </span>
        </div>
        <dl className="mt-3 space-y-2 text-xs text-slate-600">
          <InfoRow label="Retrieved context" value={retrieval?.context_items?.length ?? 0} />
          <InfoRow label="Retrieval status" value={formatType(retrieval?.readiness_status)} />
          <InfoRow label="Total tokens" value={result.total_tokens ?? 0} />
          <InfoRow label="Latency" value={`${result.latency_ms ?? 0} ms`} />
        </dl>
      </div>

      {answer ? (
        <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
          <p className="font-semibold text-slate-950">Grounded answer</p>
          <p className="mt-2 whitespace-pre-wrap leading-6 text-slate-700">{answer.answer}</p>
          <dl className="mt-3 space-y-2 text-xs text-slate-600">
            <InfoRow label="Uncertainty" value={formatType(answer.uncertainty)} />
            <InfoRow label="Insufficient evidence" value={answer.insufficient_evidence ? "Yes" : "No"} />
            <InfoRow label="Citations" value={answer.citations?.length ?? 0} />
          </dl>
        </div>
      ) : null}

      {retrieval?.context_items?.length ? (
        <div className="space-y-3">
          {retrieval.context_items.slice(0, 4).map((item) => (
            <div key={`${item.rank}-${item.system_native_id ?? item.canonical_source_id}`} className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <p className="font-semibold text-slate-950">Rank {item.rank}</p>
                <p className="text-xs text-slate-500">Score {formatScore(item.score)}</p>
              </div>
              <p className="mt-2 line-clamp-4 leading-6 text-slate-600">{item.content_preview}</p>
              <p className="mt-2 text-xs text-slate-500">
                {formatType(item.source_type)} - {formatType(item.source_subtype)}
              </p>
            </div>
          ))}
        </div>
      ) : null}

      {result.warnings?.map((warning) => (
        <div key={warning} className="flex gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{warning}</span>
        </div>
      ))}
    </div>
  );
}

function Notice({ tone, message }) {
  const classes =
    tone === "success"
      ? "border-green-200 bg-green-50 text-green-700"
      : "border-red-200 bg-red-50 text-red-700";

  return <div className={`mt-6 rounded-lg border px-4 py-3 text-sm ${classes}`}>{message}</div>;
}

function LoadingLine({ label }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
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

function InfoRow({ label, value }) {
  const displayValue =
    value === null || value === undefined || value === "" ? "Not set" : value;

  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="break-words text-right font-medium text-slate-800">{displayValue}</dd>
    </div>
  );
}

function formatStorageValue(value) {
  if (value === null || value === undefined) {
    return "Not set";
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return value;
}

function formatScore(value) {
  if (typeof value !== "number") {
    return "n/a";
  }

  return value.toFixed(4);
}

function formatType(value = "") {
  if (value === null || value === undefined || value === "") {
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

function getPatientId() {
  return window.location.pathname.split("/")[2] || "";
}

function getConversationId() {
  return window.location.pathname.split("/")[4] || null;
}
