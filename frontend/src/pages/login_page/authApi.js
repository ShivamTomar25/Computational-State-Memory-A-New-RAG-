export class AuthenticationError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "AuthenticationError";
    this.status = status;
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const AUTH_SESSION_KEY = "sustha.doctor.auth";

function getStorageItems() {
  if (typeof window === "undefined") {
    return [];
  }

  return [window.sessionStorage, window.localStorage];
}

function getApiUrl(path) {
  return `${API_BASE_URL}${path}`;
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
    return "Invalid email or password.";
  }

  if (response.status === 403) {
    return "This account is inactive.";
  }

  if (response.status === 409) {
    return "This doctor record already exists.";
  }

  return "The server could not complete this request.";
}

async function readResponse(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  let response;

  try {
    response = await fetch(getApiUrl(path), {
      method: options.method ?? "GET",
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new AuthenticationError("Unable to reach the backend server.");
  }

  const data = await readResponse(response);

  if (!response.ok) {
    throw new AuthenticationError(
      getErrorMessage(response, data),
      response.status,
    );
  }

  return data;
}

function saveAuthSession(data, rememberMe) {
  const session = {
    accessToken: data.access_token,
    tokenType: data.token_type,
    expiresInSeconds: data.expires_in_seconds,
    doctor: data.doctor,
    savedAt: new Date().toISOString(),
  };

  const storage = rememberMe ? window.localStorage : window.sessionStorage;
  const otherStorage = rememberMe ? window.sessionStorage : window.localStorage;

  otherStorage.removeItem(AUTH_SESSION_KEY);
  storage.setItem(AUTH_SESSION_KEY, JSON.stringify(session));
}

function saveDoctor(doctor) {
  for (const storage of getStorageItems()) {
    const storedValue = storage.getItem(AUTH_SESSION_KEY);

    if (!storedValue) {
      continue;
    }

    try {
      const session = JSON.parse(storedValue);
      storage.setItem(
        AUTH_SESSION_KEY,
        JSON.stringify({
          ...session,
          doctor,
        }),
      );
    } catch {
      storage.removeItem(AUTH_SESSION_KEY);
    }
  }
}

export function getAuthSession() {
  for (const storage of getStorageItems()) {
    const storedValue = storage.getItem(AUTH_SESSION_KEY);

    if (!storedValue) {
      continue;
    }

    try {
      return JSON.parse(storedValue);
    } catch {
      storage.removeItem(AUTH_SESSION_KEY);
    }
  }

  return null;
}

export function getAuthToken() {
  return getAuthSession()?.accessToken ?? null;
}

export function getStoredDoctor() {
  return getAuthSession()?.doctor ?? null;
}

export function clearAuthSession() {
  for (const storage of getStorageItems()) {
    storage.removeItem(AUTH_SESSION_KEY);
  }
}

export async function loginDoctor(payload) {
  const data = await request("/api/doctors/login", {
    method: "POST",
    body: {
      email: payload.email,
      password: payload.password,
    },
  });

  saveAuthSession(data, payload.rememberMe);

  return data;
}

export async function registerDoctor(payload) {
  return request("/api/doctors/register", {
    method: "POST",
    body: payload,
  });
}

export async function getCurrentDoctor() {
  const token = getAuthToken();

  if (!token) {
    throw new AuthenticationError("Sign in before opening this page.", 401);
  }

  const doctor = await request("/api/doctors/me", {
    token,
  });

  saveDoctor(doctor);

  return doctor;
}

export async function updateCurrentDoctor(payload) {
  const token = getAuthToken();

  if (!token) {
    throw new AuthenticationError("Sign in before saving this profile.", 401);
  }

  const doctor = await request("/api/doctors/me", {
    method: "PATCH",
    token,
    body: payload,
  });

  saveDoctor(doctor);

  return doctor;
}
