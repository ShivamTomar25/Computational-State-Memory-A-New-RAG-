import { getAuthToken } from "../pages/login_page/authApi";
import { dedupeRequest } from "../query/requestDeduper";

export class MemorySystemsApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "MemorySystemsApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  const token = getAuthToken();
  const method = options.method ?? "GET";
  const dedupeKey = method === "GET" ? `${method}:${path}:${token ?? "anonymous"}` : null;

  return dedupeRequest(dedupeKey, () => performRequest(path, options, token, method));
}

async function performRequest(path, options, token, method) {
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response;

  try {
    response = await fetch(path, {
      method,
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new MemorySystemsApiError("Unable to reach the backend server.");
  }

  const data = await readResponse(response);

  if (!response.ok) {
    throw new MemorySystemsApiError(getErrorMessage(response, data), response.status);
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
    return "Sign in before opening memory systems.";
  }

  if (response.status === 404) {
    return "Memory system or patient was not found.";
  }

  if (response.status === 422) {
    return "Review the memory-system request.";
  }

  return "The memory-system request could not be completed.";
}

function patientSystemPath(patientId, systemType, suffix = "") {
  return `/api/patients/${patientId}/memory-systems/${systemType}${suffix}`;
}

export function listMemorySystems() {
  return request("/api/memory-systems");
}

export function getLlmStatus() {
  return request("/api/llm/status");
}

export function listPatientMemorySystems(patientId) {
  return request(`/api/patients/${patientId}/memory-systems`);
}

export function initializeAllMemorySystems(patientId) {
  return request(`/api/patients/${patientId}/memory-systems/initialize-all`, {
    method: "POST",
  });
}

export function initializeMemorySystem(patientId, systemType) {
  return request(patientSystemPath(patientId, systemType, "/initialize"), {
    method: "POST",
  });
}

export function syncMemorySystem(patientId, systemType, options = {}) {
  return request(patientSystemPath(patientId, systemType, "/sync"), {
    method: "POST",
    body: options,
  });
}

export function rebuildMemorySystem(patientId, systemType, options = {}) {
  return request(patientSystemPath(patientId, systemType, "/rebuild"), {
    method: "POST",
    body: {
      confirm_rebuild: true,
      ...options,
    },
  });
}

export function getMemorySystemStatus(patientId, systemType) {
  return request(patientSystemPath(patientId, systemType, "/status"));
}

export function getMemorySystemStatistics(patientId, systemType) {
  return request(patientSystemPath(patientId, systemType, "/statistics"));
}

export function listIngestionRuns(patientId, systemType) {
  return request(patientSystemPath(patientId, systemType, "/runs"));
}

export function retrieveMemoryContext(patientId, systemType, payload) {
  return request(patientSystemPath(patientId, systemType, "/retrieve"), {
    method: "POST",
    body: payload,
  });
}

export function createSystemConversation(patientId, systemType, payload = {}) {
  return request(patientSystemPath(patientId, systemType, "/conversations"), {
    method: "POST",
    body: payload,
  });
}

export function listSystemConversations(patientId, systemType) {
  return request(patientSystemPath(patientId, systemType, "/conversations"));
}

export function getSystemMessages(patientId, systemType, conversationId) {
  return request(patientSystemPath(patientId, systemType, `/conversations/${conversationId}/messages`));
}

export function postSystemMessage(patientId, systemType, conversationId, content) {
  return request(patientSystemPath(patientId, systemType, `/conversations/${conversationId}/messages`), {
    method: "POST",
    body: { content },
  });
}
