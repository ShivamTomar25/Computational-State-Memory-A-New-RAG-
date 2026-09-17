import { getAuthToken } from "../pages/login_page/authApi";
import { dedupeRequest } from "../query/requestDeduper";

export class EvaluationApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "EvaluationApiError";
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
    throw new EvaluationApiError("Unable to reach the backend server.");
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new EvaluationApiError(getErrorMessage(response, data), response.status);
  }

  return data;
}

function getErrorMessage(response, data) {
  if (typeof data?.detail === "string") {
    return data.detail;
  }

  if (response.status === 401) {
    return "Sign in before opening evaluation.";
  }

  return "The evaluation request could not be completed.";
}

export function listEvaluationMetrics() {
  return request("/api/evaluation/metrics");
}

export function listEvaluationDatasets() {
  return request("/api/evaluation/datasets");
}

export function validateEvaluationDatasets() {
  return request("/api/evaluation/datasets/validate", { method: "POST" });
}

export function listEvaluationExperiments() {
  return request("/api/evaluation/experiments");
}

export function createEvaluationExperiment(payload) {
  return request("/api/evaluation/experiments", {
    method: "POST",
    body: payload,
  });
}

export function startEvaluationExperiment(experimentId) {
  return request(`/api/evaluation/experiments/${experimentId}/start`, {
    method: "POST",
  });
}

export function getEvaluationProgress(experimentId) {
  return request(`/api/evaluation/experiments/${experimentId}/progress`);
}

export function getEvaluationResults(experimentId) {
  return request(`/api/evaluation/experiments/${experimentId}/results`);
}

export function getEvaluationClaims(experimentId) {
  return request(`/api/evaluation/experiments/${experimentId}/claims`);
}

export function getEvaluationCitations(experimentId) {
  return request(`/api/evaluation/experiments/${experimentId}/citations`);
}

export function getEvaluationHallucinations(experimentId) {
  return request(`/api/evaluation/experiments/${experimentId}/hallucinations`);
}

export function createEvaluationExport(experimentId, exportType) {
  return request(`/api/evaluation/experiments/${experimentId}/exports`, {
    method: "POST",
    body: { export_type: exportType },
  });
}
