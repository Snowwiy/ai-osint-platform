import { lazy, Suspense } from "react";
import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { FeatureGate } from "./components/FeatureGate";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { RouteErrorFallback } from "./components/RouteErrorFallback";
import { LoadingBlock } from "./components/StateBlock";

const AdminAuditPage = lazy(() => import("./pages/AdminAuditPage").then((module) => ({ default: module.AdminAuditPage })));
const AdminSettingsPage = lazy(() => import("./pages/AdminSettingsPage").then((module) => ({ default: module.AdminSettingsPage })));
const AdminUsersPage = lazy(() => import("./pages/AdminUsersPage").then((module) => ({ default: module.AdminUsersPage })));
const AnalystWorkloadPage = lazy(() => import("./pages/AnalystWorkloadPage").then((module) => ({ default: module.AnalystWorkloadPage })));
const AnalysisPage = lazy(() => import("./pages/AnalysisPage").then((module) => ({ default: module.AnalysisPage })));
const BookmarksPage = lazy(() => import("./pages/BookmarksPage").then((module) => ({ default: module.BookmarksPage })));
const ClosurePage = lazy(() => import("./pages/ClosurePage").then((module) => ({ default: module.ClosurePage })));
const CollaborationPage = lazy(() => import("./pages/CollaborationPage").then((module) => ({ default: module.CollaborationPage })));
const CorrelationsPage = lazy(() => import("./pages/CorrelationsPage").then((module) => ({ default: module.CorrelationsPage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })));
const DataQualityPage = lazy(() => import("./pages/DataQualityPage").then((module) => ({ default: module.DataQualityPage })));
const DemoChecklistPage = lazy(() => import("./pages/DemoChecklistPage").then((module) => ({ default: module.DemoChecklistPage })));
const EvidenceIntelligencePage = lazy(() => import("./pages/EvidenceIntelligencePage").then((module) => ({ default: module.EvidenceIntelligencePage })));
const EngagementsPage = lazy(() => import("./pages/EngagementsPage").then((module) => ({ default: module.EngagementsPage })));
const ExecutiveDashboardPage = lazy(() => import("./pages/ExecutiveDashboardPage").then((module) => ({ default: module.ExecutiveDashboardPage })));
const FindingsPage = lazy(() => import("./pages/FindingsPage").then((module) => ({ default: module.FindingsPage })));
const GlobalTimelinePage = lazy(() => import("./pages/GlobalTimelinePage").then((module) => ({ default: module.GlobalTimelinePage })));
const InvestigationDetailPage = lazy(() => import("./pages/InvestigationDetailPage").then((module) => ({ default: module.InvestigationDetailPage })));
const InvestigationsPage = lazy(() => import("./pages/InvestigationsPage").then((module) => ({ default: module.InvestigationsPage })));
const KnowledgeSearchPage = lazy(() => import("./pages/KnowledgeSearchPage").then((module) => ({ default: module.KnowledgeSearchPage })));
const LoginPage = lazy(() => import("./pages/LoginPage").then((module) => ({ default: module.LoginPage })));
const MembersPage = lazy(() => import("./pages/MembersPage").then((module) => ({ default: module.MembersPage })));
const NotesPage = lazy(() => import("./pages/NotesPage").then((module) => ({ default: module.NotesPage })));
const NotificationsPage = lazy(() => import("./pages/NotificationsPage").then((module) => ({ default: module.NotificationsPage })));
const OperationsCenterPage = lazy(() => import("./pages/OperationsCenterPage").then((module) => ({ default: module.OperationsCenterPage })));
const OperationsQueuePage = lazy(() => import("./pages/OperationsQueuePage").then((module) => ({ default: module.OperationsQueuePage })));
const PlaybooksPage = lazy(() => import("./pages/PlaybooksPage").then((module) => ({ default: module.PlaybooksPage })));
const ReconResultsPage = lazy(() => import("./pages/ReconResultsPage").then((module) => ({ default: module.ReconResultsPage })));
const ReportingCenterPage = lazy(() => import("./pages/ReportingCenterPage").then((module) => ({ default: module.ReportingCenterPage })));
const ReportsPage = lazy(() => import("./pages/ReportsPage").then((module) => ({ default: module.ReportsPage })));
const ReviewBoardPage = lazy(() => import("./pages/ReviewBoardPage").then((module) => ({ default: module.ReviewBoardPage })));
const TargetsPage = lazy(() => import("./pages/TargetsPage").then((module) => ({ default: module.TargetsPage })));
const TasksPage = lazy(() => import("./pages/TasksPage").then((module) => ({ default: module.TasksPage })));
const ThreatIntelligencePage = lazy(() => import("./pages/ThreatIntelligencePage").then((module) => ({ default: module.ThreatIntelligencePage })));
const TimelinePage = lazy(() => import("./pages/TimelinePage").then((module) => ({ default: module.TimelinePage })));

const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
    errorElement: <RouteErrorFallback />,
  },
  {
    element: <ProtectedRoute />,
    errorElement: <RouteErrorFallback />,
    children: [
      {
        element: <AppShell />,
        errorElement: <RouteErrorFallback />,
        children: [
          {
            index: true,
            element: (
              <FeatureGate feature="enable_advanced_dashboard">
                <DashboardPage />
              </FeatureGate>
            ),
          },
          {
            path: "executive",
            element: (
              <FeatureGate feature="enable_advanced_dashboard">
                <ExecutiveDashboardPage />
              </FeatureGate>
            ),
          },
          {
            path: "operations/queue",
            element: (
              <FeatureGate feature="enable_advanced_dashboard">
                <OperationsQueuePage />
              </FeatureGate>
            ),
          },
          {
            path: "operations/analysts",
            element: (
              <FeatureGate feature="enable_advanced_dashboard">
                <AnalystWorkloadPage />
              </FeatureGate>
            ),
          },
          {
            path: "operations/timeline",
            element: (
              <FeatureGate feature="enable_advanced_dashboard">
                <GlobalTimelinePage />
              </FeatureGate>
            ),
          },
          {
            path: "operations/collaboration",
            element: (
              <FeatureGate feature="enable_collaboration">
                <CollaborationPage />
              </FeatureGate>
            ),
          },
          {
            path: "reports",
            element: (
              <FeatureGate feature="enable_report_exports">
                <ReportingCenterPage />
              </FeatureGate>
            ),
          },
          { path: "admin/audit", element: <AdminAuditPage /> },
          { path: "admin/users", element: <AdminUsersPage /> },
          { path: "admin/settings", element: <AdminSettingsPage /> },
          { path: "admin/operations", element: <OperationsCenterPage /> },
          { path: "admin/data-quality", element: <DataQualityPage /> },
          { path: "admin/demo-checklist", element: <DemoChecklistPage /> },
          { path: "investigations", element: <InvestigationsPage /> },
          { path: "engagements", element: <EngagementsPage /> },
          { path: "evidence-intelligence", element: <EvidenceIntelligencePage /> },
          { path: "threat-intelligence", element: <ThreatIntelligencePage /> },
          { path: "knowledge", element: <KnowledgeSearchPage /> },
          { path: "review-board", element: <ReviewBoardPage /> },
          { path: "notifications", element: <NotificationsPage /> },
          {
            path: "investigations/:investigationId",
            children: [
              { index: true, element: <InvestigationDetailPage /> },
              { path: "members", element: <MembersPage /> },
              { path: "targets", element: <TargetsPage /> },
              { path: "notes", element: <NotesPage /> },
              { path: "bookmarks", element: <BookmarksPage /> },
              {
                path: "playbooks",
                element: (
                  <FeatureGate feature="enable_playbooks">
                    <PlaybooksPage />
                  </FeatureGate>
                ),
              },
              { path: "tasks", element: <TasksPage /> },
              { path: "recon", element: <ReconResultsPage /> },
              { path: "findings", element: <FindingsPage /> },
              { path: "timeline", element: <TimelinePage /> },
              { path: "correlations", element: <CorrelationsPage /> },
              { path: "iocs", element: <ThreatIntelligencePage /> },
              {
                path: "reports",
                element: (
                  <FeatureGate feature="enable_report_exports">
                    <ReportsPage />
                  </FeatureGate>
                ),
              },
              { path: "closure", element: <ClosurePage /> },
              {
                path: "analysis",
                element: (
                  <FeatureGate feature="enable_ai_analysis">
                    <AnalysisPage />
                  </FeatureGate>
                ),
              },
            ],
          },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);

export function App(): JSX.Element {
  return (
    <Suspense fallback={<LoadingBlock label="Opening workspace" />}>
      <RouterProvider router={router} />
    </Suspense>
  );
}
