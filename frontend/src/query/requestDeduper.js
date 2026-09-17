const inFlightRequests = new Map();

export function dedupeRequest(key, factory) {
  if (!key) {
    return factory();
  }

  const existing = inFlightRequests.get(key);

  if (existing) {
    return existing;
  }

  const request = factory().finally(() => {
    inFlightRequests.delete(key);
  });
  inFlightRequests.set(key, request);
  return request;
}

export function getInFlightRequestCount() {
  return inFlightRequests.size;
}
