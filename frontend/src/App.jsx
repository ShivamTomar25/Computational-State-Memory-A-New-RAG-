import { Suspense, lazy, useEffect, useState } from "react";

import { RouteSkeleton } from "./components/performance/RouteSkeleton";
import { mark, measure } from "./performance/marks";
import { recordFrontendMeasurement } from "./performance/metrics";
import { prefetchRouteWhenIdle } from "./performance/prefetch";

const LoginPage = lazy(() => import("./pages/login_page/LoginPage").then((module) => ({ default: module.LoginPage })));
const RegisterDoctorPage = lazy(() => import("./pages/doctor_register/RegisterDoctorPage").then((module) => ({ default: module.RegisterDoctorPage })));
const DoctorPatientsPage = lazy(() => import("./pages/doctor_patients/DoctorPatientsPage").then((module) => ({ default: module.DoctorPatientsPage })));
const CreatePatientPage = lazy(() => import("./pages/create_patient/CreatePatientPage").then((module) => ({ default: module.CreatePatientPage })));
const PatientWorkspacePage = lazy(() => import("./pages/patient_workspace/PatientWorkspacePage").then((module) => ({ default: module.PatientWorkspacePage })));
const UploadDocumentPage = lazy(() => import("./pages/upload_document/UploadDocumentPage").then((module) => ({ default: module.UploadDocumentPage })));
const PatientInformationPage = lazy(() => import("./pages/patient_information/PatientInformationPage").then((module) => ({ default: module.PatientInformationPage })));
const RagResponsePage = lazy(() => import("./pages/rag_response/RagResponsePage").then((module) => ({ default: module.RagResponsePage })));
const CompareSystemsPage = lazy(() => import("./pages/compare_systems/CompareSystemsPage").then((module) => ({ default: module.CompareSystemsPage })));
const SystemWorkspacePage = lazy(() => import("./pages/system_workspace/SystemWorkspacePage").then((module) => ({ default: module.SystemWorkspacePage })));
const PatientTimelinePage = lazy(() => import("./pages/patient_timeline/PatientTimelinePage").then((module) => ({ default: module.PatientTimelinePage })));
const MedicalDocumentViewerPage = lazy(() => import("./pages/medical_document_viewer/MedicalDocumentViewerPage").then((module) => ({ default: module.MedicalDocumentViewerPage })));
const ComputationalStateMemoryPage = lazy(() => import("./pages/computational_state_memory/ComputationalStateMemoryPage").then((module) => ({ default: module.ComputationalStateMemoryPage })));
const ConversationHistoryPage = lazy(() => import("./pages/conversation_history/ConversationHistoryPage").then((module) => ({ default: module.ConversationHistoryPage })));
const EvidenceExplorerPage = lazy(() => import("./pages/evidence_explorer/EvidenceExplorerPage").then((module) => ({ default: module.EvidenceExplorerPage })));
const MemorySystemsPage = lazy(() => import("./pages/memory_systems/MemorySystemsPage").then((module) => ({ default: module.MemorySystemsPage })));
const ResearchDashboardPage = lazy(() => import("./pages/research_dashboard/ResearchDashboardPage").then((module) => ({ default: module.ResearchDashboardPage })));
const ExperimentManagementPage = lazy(() => import("./pages/experiment_management/ExperimentManagementPage").then((module) => ({ default: module.ExperimentManagementPage })));
const GlobalSearchPage = lazy(() => import("./pages/global_search/GlobalSearchPage").then((module) => ({ default: module.GlobalSearchPage })));
const NotificationsCenterPage = lazy(() => import("./pages/notifications_center/NotificationsCenterPage").then((module) => ({ default: module.NotificationsCenterPage })));
const DoctorSettingsPage = lazy(() => import("./pages/doctor_settings/DoctorSettingsPage").then((module) => ({ default: module.DoctorSettingsPage })));
const SecuritySessionsPage = lazy(() => import("./pages/security_sessions/SecuritySessionsPage").then((module) => ({ default: module.SecuritySessionsPage })));
const AuditLogPage = lazy(() => import("./pages/audit_log/AuditLogPage").then((module) => ({ default: module.AuditLogPage })));
const AdminPortalPage = lazy(() => import("./pages/administration_portal/AdminPortalPage").then((module) => ({ default: module.AdminPortalPage })));
const OrganizationRolesPage = lazy(() => import("./pages/organization_roles/OrganizationRolesPage").then((module) => ({ default: module.OrganizationRolesPage })));
const BackgroundJobsPage = lazy(() => import("./pages/background_jobs/BackgroundJobsPage").then((module) => ({ default: module.BackgroundJobsPage })));
const ExportCenterPage = lazy(() => import("./pages/export_center/ExportCenterPage").then((module) => ({ default: module.ExportCenterPage })));
const FeedbackReviewPage = lazy(() => import("./pages/feedback_review/FeedbackReviewPage").then((module) => ({ default: module.FeedbackReviewPage })));
const SystemHealthPage = lazy(() => import("./pages/system_health/SystemHealthPage").then((module) => ({ default: module.SystemHealthPage })));
const HelpCenterPage = lazy(() => import("./pages/help_center/HelpCenterPage").then((module) => ({ default: module.HelpCenterPage })));
const ErrorPage = lazy(() => import("./pages/error_pages/ErrorPage").then((module) => ({ default: module.ErrorPage })));
const FrontendQualityPage = lazy(() => import("./pages/frontend_quality/FrontendQualityPage").then((module) => ({ default: module.FrontendQualityPage })));
const EvaluationDashboardPage = lazy(() => import("./pages/EvaluationDashboard/EvaluationDashboardPage").then((module) => ({ default: module.EvaluationDashboardPage })));
const ExperimentCreatePage = lazy(() => import("./pages/ExperimentCreate/ExperimentCreatePage").then((module) => ({ default: module.ExperimentCreatePage })));
const ExperimentDetailPage = lazy(() => import("./pages/ExperimentDetail/ExperimentDetailPage").then((module) => ({ default: module.ExperimentDetailPage })));
const DatasetManagementPage = lazy(() => import("./pages/DatasetManagement/DatasetManagementPage").then((module) => ({ default: module.DatasetManagementPage })));
const HumanEvaluationPage = lazy(() => import("./pages/HumanEvaluation/HumanEvaluationPage").then((module) => ({ default: module.HumanEvaluationPage })));

export default function App() {
  const [, setRouteVersion] = useState(0);

  useEffect(() => {
    function refreshRoute() {
      mark("route-change-start");
      setRouteVersion((version) => version + 1);
      window.requestAnimationFrame(() => {
        mark("route-change-painted");
        const duration = measure("route-change", "route-change-start", "route-change-painted");
        recordFrontendMeasurement("route-change", duration, { path: window.location.pathname });
      });
    }

    window.addEventListener("popstate", refreshRoute);
    window.addEventListener("sustha:navigate", refreshRoute);

    return () => {
      window.removeEventListener("popstate", refreshRoute);
      window.removeEventListener("sustha:navigate", refreshRoute);
    };
  }, []);

  useEffect(() => {
    const path = window.location.pathname;

    for (const nextPath of getLikelyNextRoutes(path)) {
      prefetchRouteWhenIdle(nextPath);
    }
  }, []);

  return <Suspense fallback={<RouteSkeleton label="Loading page" />}>{resolveRoute()}</Suspense>;
}

function resolveRoute() {
  const path = window.location.pathname;
  const segments = path.split("/").filter(Boolean);
  const isPatientRoute = segments[0] === "patients" && Boolean(segments[1]);

  if (path === "/") {
    return <LoginPage />;
  }

  if (path === "/doctor-register") {
    return <RegisterDoctorPage />;
  }

  if (path === "/create-patient") {
    return <CreatePatientPage />;
  }

  if (path === "/patients") {
    return <DoctorPatientsPage />;
  }

  if (path === "/evidence") {
    return <EvidenceExplorerPage />;
  }

  if (path === "/memory-systems") {
    return <MemorySystemsPage />;
  }

  if (path === "/research") {
    return <ResearchDashboardPage />;
  }

  if (path === "/evaluation") {
    return <EvaluationDashboardPage />;
  }

  if (path === "/evaluation/experiments/new") {
    return <ExperimentCreatePage />;
  }

  if (path.startsWith("/evaluation/experiments/")) {
    return <ExperimentDetailPage />;
  }

  if (path === "/evaluation/datasets") {
    return <DatasetManagementPage />;
  }

  if (path === "/evaluation/review") {
    return <HumanEvaluationPage />;
  }

  if (path.startsWith("/research/experiments")) {
    return <ExperimentManagementPage />;
  }

  if (path === "/research/feedback") {
    return <FeedbackReviewPage />;
  }

  if (path === "/search") {
    return <GlobalSearchPage />;
  }

  if (path === "/notifications") {
    return <NotificationsCenterPage />;
  }

  if (path === "/settings/security") {
    return <SecuritySessionsPage />;
  }

  if (path === "/settings") {
    return <DoctorSettingsPage />;
  }

  if (path === "/exports") {
    return <ExportCenterPage />;
  }

  if (path === "/status") {
    return <SystemHealthPage />;
  }

  if (path === "/help" || path === "/help/getting-started") {
    return <HelpCenterPage />;
  }

  if (path.startsWith("/error/")) {
    return <ErrorPage />;
  }

  if (path === "/admin/audit") {
    return <AuditLogPage />;
  }

  if (path === "/admin/organizations" || path === "/admin/roles") {
    return <OrganizationRolesPage />;
  }

  if (path === "/admin/jobs") {
    return <BackgroundJobsPage />;
  }

  if (path === "/admin/system-health") {
    return <SystemHealthPage />;
  }

  if (path === "/admin/frontend-quality") {
    return <FrontendQualityPage />;
  }

  if (path === "/admin") {
    return <AdminPortalPage />;
  }

  if (isPatientRoute && segments[2] === "documents" && segments[3]) {
    return <MedicalDocumentViewerPage />;
  }

  if (isPatientRoute && segments[2] === "documents") {
    return <UploadDocumentPage />;
  }

  if (isPatientRoute && segments[2] === "timeline") {
    return <PatientTimelinePage />;
  }

  if (isPatientRoute && segments[2] === "evidence") {
    return <EvidenceExplorerPage />;
  }

  if (isPatientRoute && segments[2] === "memory-systems") {
    return <CompareSystemsPage />;
  }

  if (isPatientRoute && segments[2] === "systems" && segments[3]) {
    return <SystemWorkspacePage />;
  }

  if (isPatientRoute && segments[2] === "csm") {
    return <ComputationalStateMemoryPage />;
  }

  if (isPatientRoute && segments[2] === "information") {
    return <PatientInformationPage />;
  }

  if (isPatientRoute && segments[2] === "chat") {
    return <ConversationHistoryPage />;
  }

  if (isPatientRoute && segments[2] === "rag-response") {
    return <RagResponsePage />;
  }

  if (isPatientRoute && segments[2] === "compare") {
    return <CompareSystemsPage />;
  }

  if (path.startsWith("/patients/")) {
    return <PatientWorkspacePage />;
  }

  return <ErrorPage code="404" />;
}

function getLikelyNextRoutes(path) {
  if (path === "/") {
    return ["/patients", "/doctor-register"];
  }

  if (path === "/patients") {
    return ["/create-patient", "/research", "/status"];
  }

  if (path.startsWith("/patients/")) {
    return [
      `${path.split("/").slice(0, 3).join("/")}/chat`,
      `${path.split("/").slice(0, 3).join("/")}/documents`,
      `${path.split("/").slice(0, 3).join("/")}/memory-systems`,
    ];
  }

  return ["/patients", "/research", "/evaluation"];
}
