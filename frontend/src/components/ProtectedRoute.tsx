import { Navigate, Outlet, useLocation } from "react-router-dom";

import { LoadingBlock } from "./StateBlock";
import { useAuth } from "../lib/useAuth";

export function ProtectedRoute(): JSX.Element {
  const { isAuthenticated, isBootstrapping } = useAuth();
  const location = useLocation();

  if (isBootstrapping) {
    return (
      <main className="min-h-screen p-6">
        <LoadingBlock label="Opening dashboard" />
      </main>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return <Outlet />;
}
