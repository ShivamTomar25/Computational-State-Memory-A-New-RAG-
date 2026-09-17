import { useEffect, useRef, useState } from "react";

export function useJobProgress(fetchStatus, { active = true, intervalMs = 2000 } = {}) {
  const [status, setStatus] = useState(null);
  const visibleRef = useRef(typeof document === "undefined" ? true : !document.hidden);

  useEffect(() => {
    function updateVisibility() {
      visibleRef.current = !document.hidden;
    }

    document.addEventListener("visibilitychange", updateVisibility);
    return () => document.removeEventListener("visibilitychange", updateVisibility);
  }, []);

  useEffect(() => {
    if (!active || !fetchStatus) {
      return undefined;
    }

    let cancelled = false;
    let handle = null;

    async function poll() {
      try {
        const nextStatus = await fetchStatus();

        if (!cancelled) {
          setStatus(nextStatus);
        }
      } finally {
        if (!cancelled && !isTerminal(status)) {
          handle = window.setTimeout(poll, visibleRef.current ? intervalMs : intervalMs * 4);
        }
      }
    }

    poll();

    return () => {
      cancelled = true;
      if (handle) {
        window.clearTimeout(handle);
      }
    };
  }, [active, fetchStatus, intervalMs, status]);

  return status;
}

function isTerminal(status) {
  const value = typeof status === "string" ? status : status?.status;
  return ["completed", "failed", "cancelled"].includes(value);
}
