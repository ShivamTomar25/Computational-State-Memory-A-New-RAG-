import { listPatientInformation } from "../patient_information/patientInformationApi";

export const timelinePatient = {
  id: "",
  displayName: "No patient loaded",
  systemPatientId: "Not available",
  age: "Not available",
  sex: "Not available",
  primaryCondition: "Not available",
  memoryVersion: 0,
  lastUpdated: "Not available",
};

export const timelineCategories = [
  "Documents",
  "Clinical Information",
  "Medication",
  "Diagnosis",
  "Symptom",
  "Allergy",
  "Laboratory Result",
  "Vital Sign",
  "Procedure",
  "Treatment Plan",
  "Corrections",
  "Retractions",
  "Memory Updates",
  "Conversations",
];

export const timelineEvidenceStatuses = [
  "Active",
  "Superseded",
  "Retracted",
  "Contested",
  "Pending Review",
];

export const timelineSourceTypes = [
  "Doctor Observation",
  "Patient Report",
  "Uploaded Document",
  "Laboratory System",
  "Hospital Record",
  "External Clinician",
  "System Generated",
];

export const timelineEvents = [];
const timelineCachePrefix = "sustha:timeline:";

const resourceConfigs = {
  encounters: {
    category: "Clinical Information",
    sourceTitle: "Encounter record",
    title: (record) => record.chief_complaint || `${toTitle(record.encounter_type)} encounter`,
    summary: (record) => record.summary || record.location || `Encounter status: ${toTitle(record.status)}`,
    effectiveAt: (record) => record.started_at,
    status: (record) => toTitle(record.status),
    originalText: (record) => [
      record.chief_complaint,
      record.summary,
      record.location ? `Location: ${record.location}` : null,
    ],
  },
  conditions: {
    category: "Diagnosis",
    sourceTitle: "Condition record",
    title: (record) => record.name,
    summary: (record) => [
      record.category ? `Category: ${toTitle(record.category)}` : null,
      record.clinical_status ? `Status: ${toTitle(record.clinical_status)}` : null,
      record.severity ? `Severity: ${toTitle(record.severity)}` : null,
      record.notes,
    ],
    effectiveAt: (record) => record.onset_date || record.recorded_at,
    status: (record) => toTitle(record.verification_status || record.clinical_status),
    originalText: (record) => [
      record.name,
      record.code ? `Code: ${record.code}` : null,
      record.notes,
      record.source_reference ? `Source reference: ${record.source_reference}` : null,
    ],
  },
  medications: {
    category: "Medication",
    sourceTitle: "Medication record",
    title: (record) => record.medication_name,
    summary: (record) => [
      record.dosage_value || record.dosage_unit
        ? `Dose: ${[record.dosage_value, record.dosage_unit].filter(Boolean).join(" ")}`
        : null,
      record.frequency ? `Frequency: ${record.frequency}` : null,
      record.medication_status ? `Status: ${toTitle(record.medication_status)}` : null,
      record.reason,
      record.instructions,
    ],
    effectiveAt: (record) => record.start_date || record.recorded_at,
    status: (record) => toTitle(record.medication_status),
    originalText: (record) => [
      record.medication_name,
      record.generic_name ? `Generic: ${record.generic_name}` : null,
      record.instructions,
      record.reason,
    ],
  },
  allergies: {
    category: "Allergy",
    sourceTitle: "Allergy record",
    title: (record) => record.substance,
    summary: (record) => [
      record.reaction ? `Reaction: ${record.reaction}` : null,
      record.severity ? `Severity: ${toTitle(record.severity)}` : null,
      record.criticality ? `Criticality: ${toTitle(record.criticality)}` : null,
      record.notes,
    ],
    effectiveAt: (record) => record.onset_date || record.recorded_at,
    status: (record) => toTitle(record.verification_status || record.clinical_status),
    originalText: (record) => [
      record.substance,
      record.reaction,
      record.notes,
      record.source_reference ? `Source reference: ${record.source_reference}` : null,
    ],
  },
  measurements: {
    category: "Vital Sign",
    sourceTitle: "Measurement record",
    title: (record) => record.observation_name,
    summary: (record) => [
      `Value: ${formatMeasurementValue(record)}`,
      record.interpretation ? `Interpretation: ${toTitle(record.interpretation)}` : null,
      record.notes,
    ],
    effectiveAt: (record) => record.observed_at,
    status: (record) => toTitle(record.status),
    originalText: (record) => [
      record.observation_name,
      `Value: ${formatMeasurementValue(record)}`,
      record.notes,
    ],
  },
  notes: {
    category: "Clinical Information",
    sourceTitle: "Clinical note",
    title: (record) => record.title || `${toTitle(record.note_type)} note`,
    summary: (record) => record.content,
    effectiveAt: (record) => record.authored_at,
    status: (record) => toTitle(record.status),
    originalText: (record) => record.content,
  },
};

export async function fetchPatientTimeline(patientId) {
  const responses = await Promise.all(
    Object.keys(resourceConfigs).map(async (resource) => {
      const response = await listPatientInformation(patientId, resource, false);
      return response.items.map((record) => toTimelineEvent(resource, record));
    }),
  );

  return responses.flat();
}

export function getCachedPatientTimelineEvents(patientId) {
  try {
    const raw = window.sessionStorage.getItem(cacheKey(patientId));
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function cachePatientTimelineRecord(patientId, resource, record) {
  const event = toTimelineEvent(resource, record);
  const cached = getCachedPatientTimelineEvents(patientId).filter(
    (item) => item.id !== event.id,
  );
  const next = [event, ...cached].slice(0, 100);

  try {
    window.sessionStorage.setItem(cacheKey(patientId), JSON.stringify(next));
  } catch {
    // Timeline caching is a UX optimization only.
  }
}

function cacheKey(patientId) {
  return `${timelineCachePrefix}${patientId}`;
}

function toTimelineEvent(resource, record) {
  const config = resourceConfigs[resource];
  const effectiveAt = normalizeDateTime(config.effectiveAt(record));
  const ingestedAt = normalizeDateTime(record.created_at || record.recorded_at || effectiveAt);
  const summary = valueToText(config.summary(record));
  const originalText = valueToText(config.originalText(record));

  return {
    id: `${resource}-${record.id}`,
    category: config.category,
    title: config.title(record) || "Clinical record",
    summary: summary || "No additional details recorded.",
    effectiveAt,
    ingestedAt,
    sourceType: toTitle(record.source_type || "doctor_observation"),
    sourceTitle: config.sourceTitle,
    sourceId: record.source_reference || `${resource}-${record.id}`,
    evidenceStatus: record.is_active ? "Active" : "Retracted",
    verificationStatus: config.status(record) || "Confirmed by Doctor",
    patientMemoryVersion: 0,
    addedBy: { name: "Doctor" },
    originalText: originalText || summary || config.title(record) || "Clinical record",
    relatedEvidenceIds: [`${resource}-${record.id}`],
    causedStateIds: [],
    processingStatus: "Ready",
    isSystemActivity: false,
  };
}

function normalizeDateTime(value) {
  if (!value) {
    return null;
  }

  const text = String(value);
  return text.includes("T") ? text : `${text}T00:00:00`;
}

function valueToText(value) {
  if (Array.isArray(value)) {
    return value.filter(Boolean).join(". ");
  }

  return value || "";
}

function formatMeasurementValue(record) {
  return [
    record.value_numeric ?? record.value_text,
    record.unit,
  ].filter(Boolean).join(" ") || "Not recorded";
}

function toTitle(value) {
  if (!value) {
    return "";
  }

  return String(value)
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
