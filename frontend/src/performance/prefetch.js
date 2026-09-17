import { runWhenIdle } from "./idleTasks";

const routePrefetchers = [
  ["/patients", () => import("../pages/doctor_patients/DoctorPatientsPage")],
  ["/create-patient", () => import("../pages/create_patient/CreatePatientPage")],
  ["/evaluation", () => import("../pages/EvaluationDashboard/EvaluationDashboardPage")],
  ["/research", () => import("../pages/research_dashboard/ResearchDashboardPage")],
  ["/memory-systems", () => import("../pages/memory_systems/MemorySystemsPage")],
  ["/status", () => import("../pages/system_health/SystemHealthPage")],
  ["/settings", () => import("../pages/doctor_settings/DoctorSettingsPage")],
];

const prefetchedRoutes = new Set();

export function prefetchRoute(pathname) {
  if (!pathname || prefetchedRoutes.has(pathname)) {
    return Promise.resolve();
  }

  const prefetcher = getRoutePrefetcher(pathname);

  if (!prefetcher) {
    return Promise.resolve();
  }

  prefetchedRoutes.add(pathname);
  return prefetcher().catch(() => {
    prefetchedRoutes.delete(pathname);
  });
}

export function prefetchRouteWhenIdle(pathname) {
  return runWhenIdle(() => {
    prefetchRoute(pathname);
  });
}

export function navigateInstant(pathname) {
  if (!pathname || window.location.pathname === pathname) {
    return;
  }

  prefetchRoute(pathname);
  window.history.pushState({}, "", pathname);
  window.dispatchEvent(new Event("sustha:navigate"));
}

function getRoutePrefetcher(pathname) {
  const segments = pathname.split("/").filter(Boolean);

  if (segments[0] === "patients" && segments[1]) {
    if (segments[2] === "chat") {
      return () => import("../pages/conversation_history/ConversationHistoryPage");
    }

    if (segments[2] === "documents" && segments[3]) {
      return () => import("../pages/medical_document_viewer/MedicalDocumentViewerPage");
    }

    if (segments[2] === "documents") {
      return () => import("../pages/upload_document/UploadDocumentPage");
    }

    if (segments[2] === "information") {
      return () => import("../pages/patient_information/PatientInformationPage");
    }

    if (segments[2] === "timeline") {
      return () => import("../pages/patient_timeline/PatientTimelinePage");
    }

    if (segments[2] === "memory-systems" || segments[2] === "compare") {
      return () => import("../pages/compare_systems/CompareSystemsPage");
    }

    if (segments[2] === "systems" && segments[3]) {
      return () => import("../pages/system_workspace/SystemWorkspacePage");
    }

    if (segments[2] === "csm") {
      return () => import("../pages/computational_state_memory/ComputationalStateMemoryPage");
    }

    if (segments[2] === "evidence") {
      return () => import("../pages/evidence_explorer/EvidenceExplorerPage");
    }

    return () => import("../pages/patient_workspace/PatientWorkspacePage");
  }

  const match = routePrefetchers.find(([prefix]) => pathname === prefix || pathname.startsWith(prefix));

  return match?.[1] ?? null;
}
