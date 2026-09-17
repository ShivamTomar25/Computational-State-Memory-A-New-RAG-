import { queryClient } from "./queryClient";
import { queryKeys } from "./queryKeys";

export function prefetchPatient(patientId, fetcher) {
  if (!patientId || !fetcher) {
    return Promise.resolve();
  }

  return queryClient.prefetchQuery({
    queryKey: queryKeys.patients.detail(patientId),
    queryFn: () => fetcher(patientId),
  });
}

export function prefetchEvaluationResults(experimentId, fetcher) {
  if (!experimentId || !fetcher) {
    return Promise.resolve();
  }

  return queryClient.prefetchQuery({
    queryKey: queryKeys.evaluation.results(experimentId),
    queryFn: () => fetcher(experimentId),
  });
}
