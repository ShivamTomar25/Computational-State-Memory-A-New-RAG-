export const queryKeys = {
  doctor: {
    current: ["doctor", "current"],
  },
  patients: {
    lists: () => ["patients", "list"],
    list: (params) => ["patients", "list", params],
    detail: (patientId) => ["patients", "detail", patientId],
    workspace: (patientId) => ["patients", "workspace", patientId],
  },
  documents: {
    list: (patientId, params) => ["documents", patientId, "list", params],
    detail: (patientId, documentId) => ["documents", patientId, documentId],
    processing: (patientId, documentId) => ["documents", patientId, documentId, "processing"],
  },
  memorySystems: {
    registry: ["memory-systems", "registry"],
    patientSystems: (patientId) => ["memory-systems", patientId, "systems"],
    status: (patientId, systemType) => ["memory-systems", patientId, systemType, "status"],
    statistics: (patientId, systemType) => ["memory-systems", patientId, systemType, "statistics"],
    conversations: (patientId, systemType) => ["memory-systems", patientId, systemType, "conversations"],
    messages: (patientId, systemType, conversationId) => ["memory-systems", patientId, systemType, conversationId, "messages"],
  },
  evaluation: {
    datasets: ["evaluation", "datasets"],
    metrics: ["evaluation", "metrics"],
    experiments: ["evaluation", "experiments"],
    results: (experimentId) => ["evaluation", "experiments", experimentId, "results"],
  },
};
