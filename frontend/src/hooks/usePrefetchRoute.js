import { useCallback } from "react";

import { prefetchRoute } from "../performance/prefetch";

export function usePrefetchRoute(pathname) {
  return useCallback(() => {
    prefetchRoute(pathname);
  }, [pathname]);
}
