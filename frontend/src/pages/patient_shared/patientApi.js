import { getAuthToken } from "../login_page/authApi";
import { dedupeRequest } from "../../query/requestDeduper";

export class PatientApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "PatientApiError";
    this.status = status;
  }
}

function getErrorMessage(response, data) {
  if (typeof data?.detail === "string") {
    return data.detail;
  }

  if (Array.isArray(data?.detail)) {
    return data.detail
      .map((error) => error.msg)
      .filter(Boolean)
      .join(" ");
  }

  if (response.status === 401) {
    return "Sign in before managing patients.";
  }

  if (response.status === 404) {
    return "Patient not found.";
  }

  if (response.status === 409) {
    return "A patient with this patient code already exists.";
  }

  return "The patient request could not be completed.";
}

async function readResponse(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function patientRequest(path, options = {}) {
  const token = getAuthToken();
  const method = options.method ?? "GET";

  if (!token) {
    throw new PatientApiError("Sign in before managing patients.", 401);
  }

  if (method === "GET") {
    return dedupeRequest(`GET:${path}:${token}`, () =>
      performPatientRequest(path, options, token, method),
    );
  }

  return performPatientRequest(path, options, token, method);
}

async function performPatientRequest(path, options, token, method) {
  let response;


  try {
    response = await fetch(path, {
      method,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new PatientApiError("Unable to reach the backend server.");
  }

  const data = await readResponse(response);

  if (!response.ok) {
    throw new PatientApiError(
      getErrorMessage(response, data),
      response.status,
    );
  }

  return data;
}

export function listPatients({
  page = 1,
  pageSize = 20,
  search = "",
  includeArchived = false,
} = {}) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    include_archived: String(includeArchived),
  });

  if (search.trim()) {
    params.set("search", search.trim());
  }

  return patientRequest(`/api/patients?${params.toString()}`);
}

export function createPatient(payload) {
  return patientRequest("/api/patients", {
    method: "POST",
    body: payload,
  });
}

export function getPatient(patientId) {
  return patientRequest(`/api/patients/${patientId}`);
}

export function updatePatient(patientId, payload) {
  return patientRequest(`/api/patients/${patientId}`, {
    method: "PATCH",
    body: payload,
  });
}

export function archivePatient(patientId) {
  return patientRequest(`/api/patients/${patientId}/archive`, {
    method: "POST",
  });
}

export function restorePatient(patientId) {
  return patientRequest(`/api/patients/${patientId}/restore`, {
    method: "POST",
  });
}
