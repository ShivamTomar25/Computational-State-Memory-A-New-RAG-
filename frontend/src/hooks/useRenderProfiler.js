import { useEffect, useRef } from "react";

import { recordFrontendMeasurement } from "../performance/metrics";

export function useRenderProfiler(name) {
  const startedAt = useRef(performance.now());

  useEffect(() => {
    recordFrontendMeasurement(`${name}:mount`, performance.now() - startedAt.current);
  }, [name]);
}
