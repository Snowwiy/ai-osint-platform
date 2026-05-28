import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AnalysisPage } from "./pages/AnalysisPage";
import { CorrelationsPage } from "./pages/CorrelationsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { FindingsPage } from "./pages/FindingsPage";
import { InvestigationDetailPage } from "./pages/InvestigationDetailPage";
import { InvestigationsPage } from "./pages/InvestigationsPage";
import { KnowledgeSearchPage } from "./pages/KnowledgeSearchPage";
import { LoginPage } from "./pages/LoginPage";
import { ReconResultsPage } from "./pages/ReconResultsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { TargetsPage } from "./pages/TargetsPage";
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
          { path: "investigations", element: <InvestigationsPage /> },
          { path: "knowledge", element: <KnowledgeSearchPage /> },
          {
            path: "investigations/:investigationId",
            children: [
              { index: true, element: <InvestigationDetailPage /> },
              { path: "targets", element: <TargetsPage /> },
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
