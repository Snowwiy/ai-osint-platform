import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AdminAuditPage } from "./pages/AdminAuditPage";
import { AnalysisPage } from "./pages/AnalysisPage";
import { BookmarksPage } from "./pages/BookmarksPage";
import { CorrelationsPage } from "./pages/CorrelationsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { FindingsPage } from "./pages/FindingsPage";
import { InvestigationDetailPage } from "./pages/InvestigationDetailPage";
import { InvestigationsPage } from "./pages/InvestigationsPage";
import { KnowledgeSearchPage } from "./pages/KnowledgeSearchPage";
import { LoginPage } from "./pages/LoginPage";
import { MembersPage } from "./pages/MembersPage";
import { NotesPage } from "./pages/NotesPage";
import { PlaybooksPage } from "./pages/PlaybooksPage";
import { ReconResultsPage } from "./pages/ReconResultsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { TargetsPage } from "./pages/TargetsPage";
import { TasksPage } from "./pages/TasksPage";
import { TimelinePage } from "./pages/TimelinePage";

const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          { index: true, element: <DashboardPage /> },
          { path: "admin/audit", element: <AdminAuditPage /> },
          { path: "investigations", element: <InvestigationsPage /> },
          { path: "knowledge", element: <KnowledgeSearchPage /> },
          {
            path: "investigations/:investigationId",
            children: [
              { index: true, element: <InvestigationDetailPage /> },
              { path: "members", element: <MembersPage /> },
              { path: "targets", element: <TargetsPage /> },
              { path: "notes", element: <NotesPage /> },
              { path: "bookmarks", element: <BookmarksPage /> },
              { path: "playbooks", element: <PlaybooksPage /> },
              { path: "tasks", element: <TasksPage /> },
              { path: "recon", element: <ReconResultsPage /> },
              { path: "findings", element: <FindingsPage /> },
              { path: "timeline", element: <TimelinePage /> },
              { path: "correlations", element: <CorrelationsPage /> },
              { path: "reports", element: <ReportsPage /> },
              { path: "analysis", element: <AnalysisPage /> },
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
