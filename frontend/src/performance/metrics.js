const measurements = [];

export function recordFrontendMeasurement(name, durationMs, details = {}) {
  if (durationMs === null || durationMs === undefined) {
    return;
  }

  measurements.push({
    name,
    durationMs,
    details,
    recordedAt: new Date().toISOString(),
  });

  if (import.meta.env.DEV && durationMs > 100) {
    console.debug("[performance]", name, durationMs.toFixed(2), details);
  }
}

export function getFrontendMeasurements() {
  return [...measurements];
}
