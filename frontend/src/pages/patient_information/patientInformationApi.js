import { getAuthToken } from "../login_page/authApi";

export class PatientInformationApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "PatientInformationApiError";
    this.status = status;
  }
}

const resourcePaths = {
  encounters: "encounters",
  conditions: "conditions",
  medications: "medications",
  allergies: "allergies",
  measurements: "measurements",
  notes: "notes",
};

async function request(path, options = {}) {
  const token = getAuthToken();

  if (!token) {
    throw new PatientInformationApiError("Sign in before managing patient information.", 401);
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
    throw new PatientInformationApiError("Unable to reach the backend server.");
  }

  const data = await readResponse(response);

  if (!response.ok) {
    throw new PatientInformationApiError(getErrorMessage(response, data), response.status);
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

  if (response.status === 404) {
    return "Patient information not found.";
  }

  if (response.status === 409) {
    return "This clinical record cannot be changed in its current state.";
  }

  if (response.status === 422) {
    return "Review the clinical information fields.";
  }

  return "The patient information request could not be completed.";
}

function resourceUrl(patientId, resource, recordId = "") {
  const path = resourcePaths[resource];
  const suffix = recordId ? `/${recordId}` : "";

  return `/api/patients/${patientId}/${path}${suffix}`;
}

export function listPatientInformation(patientId, resource, includeArchived = false) {
  const params = new URLSearchParams({
    page: "1",
    page_size: "50",
    include_archived: String(includeArchived),
  });

  return request(`${resourceUrl(patientId, resource)}?${params.toString()}`);
}

export function createPatientInformation(patientId, resource, payload) {
  return request(resourceUrl(patientId, resource), {
    method: "POST",
    body: payload,
  });
}

export function updatePatientInformation(patientId, resource, recordId, payload) {
  return request(resourceUrl(patientId, resource, recordId), {
    method: "PATCH",
    body: payload,
  });
}

export function archivePatientInformation(patientId, resource, recordId) {
  return request(`${resourceUrl(patientId, resource, recordId)}/archive`, {
    method: "POST",
  });
}

export function restorePatientInformation(patientId, resource, recordId) {
  return request(`${resourceUrl(patientId, resource, recordId)}/restore`, {
    method: "POST",
  });
}
