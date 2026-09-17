import { QueryClient } from "@tanstack/react-query";

const staleTime = Number(import.meta.env.VITE_FRONTEND_QUERY_STALE_TIME_MS ?? 30000);
const gcTime = Number(import.meta.env.VITE_FRONTEND_QUERY_GC_TIME_MS ?? 300000);

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime,
      gcTime,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if ([400, 401, 403, 404, 409, 422].includes(error?.status)) {
          return false;
        }

        return failureCount < 2;
      },
    },
    mutations: {
      retry: false,
    },
  },
});
