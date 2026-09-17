import { getAuthToken } from "../login_page/authApi";
import { getPatient } from "../patient_shared/patientApi";
import { syncCsm } from "../computational_state_memory/csmService";

export class EvidenceExplorerApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "EvidenceExplorerApiError";
    this.status = status;
  }
}

export async function fetchPatientEvidence(patientId, { syncIfEmpty = true } = {}) {
  const [patient, evidence] = await Promise.all([
    getPatient(patientId).catch(() => null),
    request(`/api/patients/${patientId}/csm/evidence`),
  ]);

  if (syncIfEmpty && evidence.length === 0) {
    await syncCsm(patientId).catch(() => null);
    const syncedEvidence = await request(`/api/patients/${patientId}/csm/evidence`);
    return normalizeEvidenceRecords(patientId, patient, syncedEvidence);
  }

  return normalizeEvidenceRecords(patientId, patient, evidence);
}

export function buildEvidenceRelationships(records) {
  return records
    .filter((record) => record.stateId || record.reviewId)
    .map((record) => ({
      from: record.id,
      relationship: record.reviewId ? "requires review before state update" : "supports state",
      to: record.reviewId || record.stateId,
      detail: record.reviewId
        ? "Conversation evidence is waiting for doctor approval in CSM."
        : "Evidence is linked to a derived computational state.",
    }));
}

async function request(path) {
  const token = getAuthToken();

  if (!token) {
    throw new EvidenceExplorerApiError("Sign in before opening evidence.", 401);
  }

  let response;

  try {
    response = await fetch(path, {
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    throw new EvidenceExplorerApiError("Unable to reach the backend server.");
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new EvidenceExplorerApiError(getErrorMessage(response, data), response.status);
  }

  return Array.isArray(data) ? data : [];
}

function normalizeEvidenceRecords(patientId, patient, evidenceItems) {
  return evidenceItems.map((item) => {
    const sourceType = item.source_type || "Unknown";
    const status = normalizeEvidenceStatus(item.evidence_status, item.group);
    const category = categoryFromEvidence(item);
    const documentId = item.document_id || null;
    const sourceId = documentId || item.section_id || item.canonical_source_id || item.id;

    return {
      id: item.id,
      canonicalSourceId: item.canonical_source_id,
      patientId,
      patientName: patient?.full_name || "Selected patient",
      patientSystemId: patient?.patient_code || patientId,
      summary: item.source_title || category,
      originalText: item.excerpt || "No evidence excerpt was stored.",
      category,
      sourceType,
      sourceTitle: sourceTitle(item),
      sourceId,
      documentId,
      pageNumber: item.page_number,
      sectionId: item.section_id,
      conversationId: item.conversation_id,
      messageId: item.message_id,
      effectiveAt: formatDisplayDate(item.effective_date),
      ingestedAt: "Stored in CSM",
      verificationStatus: item.verification || "Unknown",
      evidenceStatus: status,
      memoryVersion: "CSM",
      derivedStateCount: item.state_id ? 1 : 0,
      citationUsageCount: 0,
      relatedEvidenceCount: 0,
      hasConflict: item.group === "Conflicting Evidence",
      stateId: item.state_id,
      reviewId: item.review_id,
      contribution: item.contribution,
    };
  });
}

function sourceTitle(item) {
  if (item.document_id) {
    return item.page_number ? `Document page ${item.page_number}` : "Uploaded document";
  }

  if (item.conversation_id) {
    return "LLM conversation";
  }

  return item.source_type || "Patient information";
}

function categoryFromEvidence(item) {
  const text = `${item.source_title || ""} ${item.contribution || ""} ${item.excerpt || ""}`.toLowerCase();

  if (text.includes("medication")) {
    return "Medication";
  }

  if (text.includes("allergy")) {
    return "Allergy";
  }

  if (text.includes("lab") || text.includes("measurement") || text.includes("observation")) {
    return "Laboratory Result";
  }

  if (text.includes("condition") || text.includes("diagnosis")) {
    return "Diagnosis";
  }

  if (item.source_type === "Document") {
    return "Document";
  }

  if (item.source_type === "Conversation") {
    return "Conversation";
  }

  return "Clinical Evidence";
}

function normalizeEvidenceStatus(status, group) {
  if (group === "Pending Review") {
    return "Pending Review";
  }

  if (status === "ActiveEvidence") {
    return "Active";
  }

  return String(status || "Unknown").replace(/([a-z])([A-Z])/g, "$1 $2");
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
