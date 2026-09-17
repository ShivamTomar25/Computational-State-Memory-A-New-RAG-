export function runWhenIdle(callback, timeout = 1500) {
  if (typeof window === "undefined") {
    return null;
  }

  if ("requestIdleCallback" in window) {
    return window.requestIdleCallback(callback, { timeout });
  }

  return window.setTimeout(callback, 1);
}

export function cancelIdleTask(handle) {
  if (!handle || typeof window === "undefined") {
    return;
  }

  if ("cancelIdleCallback" in window) {
    window.cancelIdleCallback(handle);
    return;
  }

  window.clearTimeout(handle);
}
