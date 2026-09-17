export function mark(name) {
  if (typeof performance === "undefined") {
    return;
  }

  performance.mark(name);
}

export function measure(name, startMark, endMark) {
  if (typeof performance === "undefined") {
    return null;
  }

  try {
    performance.measure(name, startMark, endMark);
    return performance.getEntriesByName(name).at(-1)?.duration ?? null;
  } catch {
    return null;
  }
}
