import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { FeatureGate } from "./components/FeatureGate";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { RouteErrorFallback } from "./components/RouteErrorFallback";
import { AdminAuditPage } from "./pages/AdminAuditPage";
import { AdminSettingsPage } from "./pages/AdminSettingsPage";
import { AnalystWorkloadPage } from "./pages/AnalystWorkloadPage";
import { AnalysisPage } from "./pages/AnalysisPage";
import { BookmarksPage } from "./pages/BookmarksPage";
import { CorrelationsPage } from "./pages/CorrelationsPage";
import { CollaborationPage } from "./pages/CollaborationPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DemoChecklistPage } from "./pages/DemoChecklistPage";
import { EvidenceIntelligencePage } from "./pages/EvidenceIntelligencePage";
import { ExecutiveDashboardPage } from "./pages/ExecutiveDashboardPage";
import { FindingsPage } from "./pages/FindingsPage";
import { GlobalTimelinePage } from "./pages/GlobalTimelinePage";
import { InvestigationDetailPage } from "./pages/InvestigationDetailPage";
import { InvestigationsPage } from "./pages/InvestigationsPage";
import { KnowledgeSearchPage } from "./pages/KnowledgeSearchPage";
import { LoginPage } from "./pages/LoginPage";
import { MembersPage } from "./pages/MembersPage";
import { NotesPage } from "./pages/NotesPage";
import { OperationsCenterPage } from "./pages/OperationsCenterPage";
import { OperationsQueuePage } from "./pages/OperationsQueuePage";
import { PlaybooksPage } from "./pages/PlaybooksPage";
import { ReconResultsPage } from "./pages/ReconResultsPage";
import { ReportingCenterPage } from "./pages/ReportingCenterPage";
import { ReportsPage } from "./pages/ReportsPage";
import { ReviewBoardPage } from "./pages/ReviewBoardPage";
import { TargetsPage } from "./pages/TargetsPage";
import { TasksPage } from "./pages/TasksPage";
import { ThreatIntelligencePage } from "./pages/ThreatIntelligencePage";
import { TimelinePage } from "./pages/TimelinePage";

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
          { path: "admin/settings", element: <AdminSettingsPage /> },
          { path: "admin/operations", element: <OperationsCenterPage /> },
          { path: "admin/demo-checklist", element: <DemoChecklistPage /> },
          { path: "investigations", element: <InvestigationsPage /> },
          { path: "evidence-intelligence", element: <EvidenceIntelligencePage /> },
          { path: "threat-intelligence", element: <ThreatIntelligencePage /> },
          { path: "knowledge", element: <KnowledgeSearchPage /> },
          { path: "review-board", element: <ReviewBoardPage /> },
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
  return <RouterProvider router={router} />;
}
