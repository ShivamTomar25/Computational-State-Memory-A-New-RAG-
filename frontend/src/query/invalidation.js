import { queryClient } from "./queryClient";
import { queryKeys } from "./queryKeys";

export function invalidatePatient(patientId) {
  queryClient.invalidateQueries({ queryKey: queryKeys.patients.detail(patientId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.patients.workspace(patientId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.patients.lists() });
}

export function invalidatePatientDocuments(patientId) {
  queryClient.invalidateQueries({ queryKey: ["documents", patientId] });
  queryClient.invalidateQueries({ queryKey: queryKeys.patients.workspace(patientId) });
}

export function invalidateMemorySystem(patientId, systemType) {
  queryClient.invalidateQueries({ queryKey: ["memory-systems", patientId, systemType] });
  queryClient.invalidateQueries({ queryKey: queryKeys.memorySystems.patientSystems(patientId) });
}

export function invalidateEvaluationExperiment(experimentId) {
  queryClient.invalidateQueries({ queryKey: queryKeys.evaluation.results(experimentId) });
  queryClient.invalidateQueries({ queryKey: queryKeys.evaluation.experiments });
}
