import { recordFrontendMeasurement } from "./metrics";

export function reportWebVitals() {
  if (typeof PerformanceObserver === "undefined") {
    return;
  }

  observeEntries("navigation");
  observeEntries("longtask");
}

function observeEntries(type) {
  try {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        recordFrontendMeasurement(type, entry.duration, { name: entry.name });
      }
    });
    observer.observe({ type, buffered: true });
  } catch {
    return null;
  }
}
