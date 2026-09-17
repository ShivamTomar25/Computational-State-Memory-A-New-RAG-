import { getAuthToken } from "../login_page/authApi";

export class DocumentApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "DocumentApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  const token = getAuthToken();

  if (!token) {
    throw new DocumentApiError("Sign in before managing documents.", 401);
  }

  const headers = {
    Authorization: `Bearer ${token}`,
    ...options.headers,
  };

  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  let response;

  try {
    response = await fetch(path, {
      method: options.method ?? "GET",
      headers,
      body:
        options.body instanceof FormData
          ? options.body
          : options.body
            ? JSON.stringify(options.body)
            : undefined,
    });
  } catch {
    throw new DocumentApiError("Unable to reach the backend server.");
  }

  const data = await readResponse(response);

  if (!response.ok) {
    throw new DocumentApiError(getErrorMessage(response, data), response.status);
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
    return "Sign in before managing documents.";
  }

  if (response.status === 404) {
    return "Document not found.";
  }

  if (response.status === 409) {
    return "This document cannot be changed in its current state.";
  }

  if (response.status === 422) {
    return "Review the document fields and selected file.";
  }

  return "The document request could not be completed.";
}

function documentsPath(patientId, suffix = "") {
  return `/api/patients/${patientId}/documents${suffix}`;
}

export function listDocuments(patientId, { includeArchived = false } = {}) {
  const params = new URLSearchParams({
    page: "1",
    page_size: "50",
    include_archived: String(includeArchived),
  });

  return request(`${documentsPath(patientId)}?${params.toString()}`);
}

export function uploadDocument(patientId, payload) {
  const formData = new FormData();
  formData.append("file", payload.file);
  formData.append("document_type", payload.documentType);

  if (payload.title) {
    formData.append("title", payload.title);
  }

  if (payload.description) {
    formData.append("description", payload.description);
  }

  if (payload.documentDate) {
    formData.append("document_date", payload.documentDate);
  }

  if (payload.encounterId) {
    formData.append("encounter_id", payload.encounterId);
  }

  return request(documentsPath(patientId, "/upload/direct"), {
    method: "POST",
    body: formData,
  });
}

export function getDocument(patientId, documentId) {
  return request(documentsPath(patientId, `/${documentId}`));
}

export function archiveDocument(patientId, documentId) {
  return request(documentsPath(patientId, `/${documentId}/archive`), {
    method: "POST",
  });
}

export function restoreDocument(patientId, documentId) {
  return request(documentsPath(patientId, `/${documentId}/restore`), {
    method: "POST",
  });
}

export function processDocument(patientId, documentId, force = false) {
  return request(documentsPath(patientId, `/${documentId}/process`), {
    method: "POST",
    body: { force },
  });
}

export function getDocumentViewUrl(patientId, documentId) {
  return request(documentsPath(patientId, `/${documentId}/view-url`), {
    method: "POST",
  });
}

export function getDocumentDownloadUrl(patientId, documentId) {
  return request(documentsPath(patientId, `/${documentId}/download-url`), {
    method: "POST",
  });
}

export function getDocumentProcessing(patientId, documentId) {
  return request(documentsPath(patientId, `/${documentId}/processing`));
}

export function getDocumentText(patientId, documentId) {
  return request(documentsPath(patientId, `/${documentId}/text`));
}

export function getDocumentPages(patientId, documentId) {
  return request(documentsPath(patientId, `/${documentId}/pages`));
}

export function getDocumentSections(patientId, documentId) {
  return request(documentsPath(patientId, `/${documentId}/sections`));
}

export function getDocumentArtifacts(patientId, documentId) {
  return request(documentsPath(patientId, `/${documentId}/artifacts`));
}

export function reconcileDocuments(patientId) {
  return request(documentsPath(patientId, "/reconcile"));
}
