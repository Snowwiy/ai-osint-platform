import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "./App";
import "./index.css";
import { AuthProvider } from "./lib/auth";
import { I18nProvider, LocalizedSurface } from "./lib/i18n";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <LocalizedSurface>
          <AuthProvider>
            <App />
          </AuthProvider>
        </LocalizedSurface>
      </I18nProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
