import { getAuthToken } from "../login_page/authApi";

export const csmPatient = {
  id: "",
  displayName: "No patient loaded",
  systemPatientId: "Not available",
  age: "Not available",
  sex: "Not available",
  primaryCondition: "Not available",
  memoryVersion: 0,
  lastUpdated: "Not available",
};

export const csmSummary = {
  availability: "CSM Not Initialized",
  stateVersion: 0,
  syncStatus: "not_initialized",
  lastStateUpdate: "Not available",
  totalActiveStates: 0,
  contestedStates: 0,
  pendingReviewStates: 0,
};

export const computationalStates = [];
export const csmEvidence = [];
export const csmHistory = [];
export const csmLineage = [];
export const csmConflicts = [];
export const csmReviews = [];

export const csmActivation = {
  id: "",
  question: "No activation loaded",
  activatedStateIds: [],
  activationOrder: [],
  activationReason: "No CSM activation data is available.",
  contextCost: "No context tokens",
  linkedAnswer: "No linked answer",
  evidenceUsed: [],
};

const csmCachePrefix = "sustha:csm:optimistic:";

export class CsmApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "CsmApiError";
    this.status = status;
  }
}

export async function fetchCsmStates(patientId) {
  const optimistic = getCachedCsmState(patientId);
  applyCsmOverview({
    summary: null,
    states: optimistic.states,
    evidence: optimistic.evidence,
    history: optimistic.history,
    lineage: optimistic.lineage,
    conflicts: [],
    reviews: [],
  });

  const overview = await fetchCsmOverview(patientId);
  const backendStateIds = new Set(overview.states.map((state) => state.id));
  const backendEvidenceIds = new Set(overview.evidence.map((evidence) => evidence.id));
  const hasPersistedCsmData = overview.states.length > 0 || overview.evidence.length > 0;
  const remainingOptimistic = {
    states: hasPersistedCsmData ? [] : optimistic.states.filter((state) => !backendStateIds.has(state.id)),
    evidence: hasPersistedCsmData ? [] : optimistic.evidence.filter((evidence) => !backendEvidenceIds.has(evidence.id)),
    history: hasPersistedCsmData ? [] : optimistic.history,
    lineage: hasPersistedCsmData ? [] : optimistic.lineage,
  };
  const mergedOverview = {
    ...overview,
    states: [...remainingOptimistic.states, ...overview.states],
    evidence: [...remainingOptimistic.evidence, ...overview.evidence],
    history: [...remainingOptimistic.history, ...overview.history],
    lineage: [...remainingOptimistic.lineage, ...overview.lineage],
  };

  setCachedCsmState(patientId, remainingOptimistic);
  applyCsmOverview(mergedOverview);
  return computationalStates;
}

export async function fetchCsmOverview(patientId) {
  const data = await request(`/api/patients/${patientId}/csm`);
  return normalizeOverview(data);
}

export async function syncCsm(patientId) {
  return request(`/api/patients/${patientId}/csm/sync`, {
    method: "POST",
    body: {
      include_patient_information: true,
      include_documents: true,
      include_conversation: true,
    },
  });
}

export async function approveCsmReview(patientId, reviewId, note = "") {
  return request(`/api/patients/${patientId}/csm/reviews/${reviewId}/approve`, {
    method: "POST",
    body: { note },
  });
}

export async function rejectCsmReview(patientId, reviewId, note = "") {
  return request(`/api/patients/${patientId}/csm/reviews/${reviewId}/reject`, {
    method: "POST",
    body: { note },
  });
}

export function getCachedCsmState(patientId) {
  try {
    const raw = window.sessionStorage.getItem(cacheKey(patientId));
    const parsed = raw ? JSON.parse(raw) : {};
    return {
      states: Array.isArray(parsed.states) ? parsed.states : [],
      evidence: Array.isArray(parsed.evidence) ? parsed.evidence : [],
      history: Array.isArray(parsed.history) ? parsed.history : [],
      lineage: Array.isArray(parsed.lineage) ? parsed.lineage : [],
    };
  } catch {
    return emptyOptimisticCache();
  }
}

export function cacheCsmRecord(patientId, resource, record) {
  mergeCachedCsmItems(patientId, [toOptimisticPatientInfoItem(resource, record)]);
}

export function cacheCsmDocument(patientId, document) {
  mergeCachedCsmItems(patientId, [toOptimisticDocumentItem(document)]);
}

export function cacheCsmMessages(patientId, systemType, conversationId, messages) {
  mergeCachedCsmItems(
    patientId,
    messages.map((message) => toOptimisticMessageItem(systemType, conversationId, message)),
  );
}

async function request(path, options = {}) {
  const token = getAuthToken();

  if (!token) {
    throw new CsmApiError("Sign in before opening Computational State Memory.", 401);
  }

  let response;

  try {
    response = await fetch(path, {
      method: options.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new CsmApiError("Unable to reach the backend server.");
  }

  const data = await readResponse(response);

  if (!response.ok) {
    throw new CsmApiError(getErrorMessage(response, data), response.status);
  }

  return data;
}

async function readResponse(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function getErrorMessage(response, data) {
  if (typeof data?.detail === "string") {
    return data.detail;
  }

  if (Array.isArray(data?.detail)) {
    return data.detail.map((error) => error.msg).filter(Boolean).join(" ");
  }

  if (response.status === 401) {
    return "Sign in before opening Computational State Memory.";
  }

  if (response.status === 404) {
    return "CSM state was not found.";
  }

  return "The CSM request could not be completed.";
}

function normalizeOverview(data) {
  return {
    summary: data?.summary ?? null,
    states: (data?.states ?? []).map(normalizeState),
    evidence: (data?.evidence ?? []).map(normalizeEvidence),
    history: (data?.history ?? []).map(normalizeHistory),
    lineage: (data?.lineage ?? []).map(normalizeLineage),
    conflicts: data?.conflicts ?? [],
    reviews: data?.reviews ?? [],
  };
}

function normalizeState(state) {
  return {
    id: state.id,
    name: state.name,
    category: state.category,
    displayValue: state.display_value,
    unit: state.unit,
    status: state.status,
    supportStatus: state.support_status,
    stateVersion: state.state_version,
    effectiveFrom: formatDisplayDate(state.effective_from),
    effectiveUntil: state.effective_until === "Not applicable" ? state.effective_until : formatDisplayDate(state.effective_until),
    lastObservedAt: formatDisplayDate(state.last_observed_at),
    updatedAt: formatDisplayDate(state.updated_at),
    nextReviewDate: state.next_review_date,
    trend: state.trend,
    uncertaintySummary: state.uncertainty_summary,
    sourceCount: state.source_count,
    activeEvidenceCount: state.active_evidence_count,
    conflictingEvidenceIds: state.conflicting_evidence_ids ?? [],
    pendingEvidenceCount: state.pending_evidence_count,
    evidenceIds: state.evidence_ids ?? [],
    upstreamDependencyIds: state.upstream_dependency_ids ?? [],
    downstreamDependencyIds: state.downstream_dependency_ids ?? [],
    activated: Boolean(state.activated),
    stale: Boolean(state.stale),
    updateOperator: state.update_operator,
    statusReason: state.status_reason,
    optimistic: Boolean(state.optimistic),
    reviewId: state.review_id,
  };
}

function normalizeEvidence(evidence) {
  return {
    id: evidence.id,
    stateId: evidence.state_id,
    reviewId: evidence.review_id,
    group: evidence.group,
    sourceTitle: evidence.source_title,
    sourceType: evidence.source_type,
    effectiveDate: formatDisplayDate(evidence.effective_date),
    excerpt: evidence.excerpt,
    evidenceStatus: evidence.evidence_status,
    verification: evidence.verification,
    contribution: evidence.contribution,
    documentId: evidence.document_id,
    pageNumber: evidence.page_number,
    sectionId: evidence.section_id,
    conversationId: evidence.conversation_id,
    messageId: evidence.message_id,
  };
}

function normalizeHistory(history) {
  return {
    id: history.id,
    stateId: history.state_id,
    effectiveAt: formatDisplayDate(history.effective_at),
    previousValue: history.previous_value,
    newValue: history.new_value,
    reason: history.reason,
    stateVersion: history.state_version,
  };
}

function normalizeLineage(node) {
  return {
    type: node.type,
    identifier: node.identifier,
    timestamp: formatDisplayDate(node.timestamp),
    actor: node.actor,
    version: node.version,
    summary: node.summary,
  };
}

function applyCsmOverview(overview) {
  computationalStates.splice(0, computationalStates.length, ...(overview.states ?? []));
  csmEvidence.splice(0, csmEvidence.length, ...(overview.evidence ?? []));
  csmHistory.splice(0, csmHistory.length, ...(overview.history ?? []));
  csmLineage.splice(0, csmLineage.length, ...(overview.lineage ?? []));
  csmConflicts.splice(0, csmConflicts.length, ...(overview.conflicts ?? []));
  csmReviews.splice(0, csmReviews.length, ...(overview.reviews ?? []));

  if (overview.summary) {
    csmSummary.availability = overview.summary.availability;
    csmSummary.stateVersion = overview.summary.state_version;
    csmSummary.syncStatus = overview.summary.sync_status;
    csmSummary.lastStateUpdate = formatDisplayDate(overview.summary.last_state_update);
    csmSummary.totalActiveStates = overview.summary.total_active_states;
    csmSummary.contestedStates = overview.summary.contested_states;
    csmSummary.pendingReviewStates = overview.summary.pending_review_states;
  } else if (overview.states?.length) {
    csmSummary.availability = "Synchronizing";
    csmSummary.stateVersion = overview.states.length;
    csmSummary.syncStatus = "optimistic_pending";
    csmSummary.lastStateUpdate = overview.states[0]?.updatedAt ?? "Not available";
    csmSummary.totalActiveStates = overview.states.filter((state) => state.status === "Active").length;
    csmSummary.contestedStates = overview.states.filter((state) => state.status === "Contested").length;
    csmSummary.pendingReviewStates = overview.states.filter((state) => state.status === "Pending Review" || state.optimistic).length;
  }
}

function mergeCachedCsmItems(patientId, items) {
  const cached = getCachedCsmState(patientId);
  const states = [
    ...items.map((item) => item.state),
    ...cached.states.filter((state) => !items.some((item) => item.state.id === state.id)),
  ].slice(0, 100);
  const evidence = [
    ...items.map((item) => item.evidence),
    ...cached.evidence.filter((evidenceItem) => !items.some((item) => item.evidence.id === evidenceItem.id)),
  ].slice(0, 100);
  const history = [
    ...items.map((item) => item.history),
    ...cached.history.filter((entry) => !items.some((item) => item.history.id === entry.id)),
  ].slice(0, 100);
  const lineage = [
    ...items.map((item) => item.lineage),
    ...cached.lineage.filter((entry) => !items.some((item) => item.lineage.identifier === entry.identifier)),
  ].slice(0, 100);

  const next = { states, evidence, history, lineage };
  setCachedCsmState(patientId, next);
  applyCsmOverview({ summary: null, ...next, conflicts: [], reviews: [] });
}

function toOptimisticPatientInfoItem(resource, record) {
  const stateId = `optimistic-info-${resource}-${record.id}`;
  const evidenceId = `optimistic-evidence-info-${resource}-${record.id}`;
  const display = patientInfoDisplay(resource, record);
  return optimisticItem({
    stateId,
    evidenceId,
    name: display.name,
    category: display.category,
    displayValue: display.value,
    sourceType: "Patient Information",
    excerpt: display.excerpt,
    status: "Pending Review",
    supportStatus: "Supported",
    updateOperator: "backend_sync_pending",
  });
}

function toOptimisticDocumentItem(document) {
  const stateId = `optimistic-document-${document.id}`;
  const evidenceId = `optimistic-evidence-document-${document.id}`;
  return optimisticItem({
    stateId,
    evidenceId,
    name: document.title || document.original_filename || "Uploaded document",
    category: "Treatment",
    displayValue: document.document_type || document.processing_status || "Document uploaded",
    sourceType: "Uploaded Document",
    excerpt: document.description || document.original_filename || "Document is queued for backend CSM sync.",
    status: "Pending Review",
    supportStatus: "Partially Supported",
    updateOperator: "document_backend_sync_pending",
  });
}

function toOptimisticMessageItem(systemType, conversationId, message) {
  const stateId = `optimistic-chat-${message.id}`;
  const evidenceId = `optimistic-evidence-chat-${message.id}`;
  return optimisticItem({
    stateId,
    evidenceId,
    name: `${toTitle(message.role)} conversation proposal`,
    category: "Symptom",
    displayValue: truncate(message.content, 90),
    sourceType: "LLM Conversation",
    excerpt: message.content,
    status: "Pending Review",
    supportStatus: "Insufficient Evidence",
    updateOperator: "conversation_review_pending",
    contribution: `${systemType} conversation ${conversationId}`,
  });
}

function optimisticItem({
  stateId,
  evidenceId,
  name,
  category,
  displayValue,
  sourceType,
  excerpt,
  status,
  supportStatus,
  updateOperator,
  contribution = "Waiting for backend CSM sync",
}) {
  const now = new Date().toISOString();
  const state = {
    id: stateId,
    name,
    category,
    displayValue,
    unit: "",
    status,
    supportStatus,
    stateVersion: 0,
    effectiveFrom: formatDisplayDate(now),
    effectiveUntil: "Not applicable",
    lastObservedAt: formatDisplayDate(now),
    updatedAt: formatDisplayDate(now),
    nextReviewDate: "Backend sync pending",
    trend: "Pending backend ingestion",
    uncertaintySummary: "Temporary optimistic item. Backend CSM sync will replace this with persisted evidence and state records.",
    sourceCount: 1,
    activeEvidenceCount: 0,
    conflictingEvidenceIds: [],
    pendingEvidenceCount: 1,
    evidenceIds: [evidenceId],
    upstreamDependencyIds: [],
    downstreamDependencyIds: [],
    activated: false,
    stale: false,
    updateOperator,
    statusReason: "optimistic_pending_backend_sync",
    optimistic: true,
  };
  const evidence = {
    id: evidenceId,
    stateId,
    group: "Pending Review",
    sourceTitle: name,
    sourceType,
    effectiveDate: formatDisplayDate(now),
    excerpt,
    evidenceStatus: "Pending Review",
    verification: "Temporary optimistic evidence",
    contribution,
  };
  const history = {
    id: `optimistic-history-${stateId}`,
    stateId,
    effectiveAt: formatDisplayDate(now),
    previousValue: "Not recorded",
    newValue: displayValue,
    reason: "Optimistic frontend placeholder",
    stateVersion: 0,
  };
  const lineage = {
    type: "Optimistic Pending Item",
    identifier: stateId,
    timestamp: formatDisplayDate(now),
    actor: "Frontend",
    version: "pending",
    summary: `${name}: ${displayValue}`,
  };

  return { state, evidence, history, lineage };
}

function patientInfoDisplay(resource, record) {
  const configs = {
    encounters: {
      category: "Treatment",
      name: record.chief_complaint || `${toTitle(record.encounter_type)} encounter`,
      value: toTitle(record.status),
      excerpt: record.summary || record.location || "Encounter saved.",
    },
    conditions: {
      category: "Diagnosis",
      name: record.name,
      value: toTitle(record.clinical_status),
      excerpt: record.notes || record.name,
    },
    medications: {
      category: "Medication",
      name: record.medication_name,
      value: [record.dosage_value, record.dosage_unit, record.frequency].filter(Boolean).join(" ") || toTitle(record.medication_status),
      excerpt: record.instructions || record.reason || record.medication_name,
    },
    allergies: {
      category: "Allergy",
      name: record.substance,
      value: record.reaction || toTitle(record.clinical_status),
      excerpt: record.notes || record.reaction || record.substance,
    },
    measurements: {
      category: "Vital Sign",
      name: record.observation_name,
      value: [record.value_numeric ?? record.value_text, record.unit].filter(Boolean).join(" ") || "Measurement recorded",
      excerpt: record.notes || record.observation_name,
    },
    notes: {
      category: "Symptom",
      name: record.title || `${toTitle(record.note_type)} note`,
      value: truncate(record.content, 90),
      excerpt: record.content,
    },
  };

  return configs[resource] ?? {
    category: "Symptom",
    name: "Patient information",
    value: "Saved",
    excerpt: "Patient information saved.",
  };
}

function setCachedCsmState(patientId, state) {
  try {
    window.sessionStorage.setItem(cacheKey(patientId), JSON.stringify(state));
  } catch {
    // Optimistic cache is non-critical.
  }
}

function emptyOptimisticCache() {
  return { states: [], evidence: [], history: [], lineage: [] };
}

function cacheKey(patientId) {
  return `${csmCachePrefix}${patientId}`;
}

function formatDisplayDate(value) {
  if (!value || value === "Not recorded" || value === "Not available") {
    return value || "Not recorded";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(date);
}

function truncate(value, maxLength) {
  const text = String(value || "");

  if (text.length <= maxLength) {
    return text;
  }

  return `${text.slice(0, maxLength - 3)}...`;
}

function toTitle(value) {
  return String(value || "")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
