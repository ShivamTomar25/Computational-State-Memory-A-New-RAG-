import { getAuthToken } from "../login_page/authApi";
import { dedupeRequest } from "../../query/requestDeduper";

export class PatientWorkspaceApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "PatientWorkspaceApiError";
    this.status = status;
  }
}

async function readResponse(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function workspaceRequest(path) {
  const token = getAuthToken();

  if (!token) {
    throw new PatientWorkspaceApiError("Sign in before opening this workspace.", 401);
  }

  let response;

  try {
    response = await fetch(path, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  } catch {
    throw new PatientWorkspaceApiError("Unable to reach the backend server.");
  }

  const data = await readResponse(response);

  if (!response.ok) {
    throw new PatientWorkspaceApiError(
      typeof data?.detail === "string" ? data.detail : "Unable to load workspace.",
      response.status,
    );
  }

  return data;
}

export function getPatientWorkspaceSummary(patientId) {
  return dedupeRequest(
    `GET:/api/patients/${patientId}/workspace-summary`,
    () => workspaceRequest(`/api/patients/${patientId}/workspace-summary`),
  );
}
