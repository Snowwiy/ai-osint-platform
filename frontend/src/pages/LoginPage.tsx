import { ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { ErrorBlock } from "../components/StateBlock";
import { useAuth } from "../lib/useAuth";

interface LocationState {
  from?: { pathname?: string };
}

export function LoginPage(): JSX.Element {
  const { isAuthenticated, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as LocationState | null;
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await login(identifier, password);
      navigate(state?.from?.pathname ?? "/", { replace: true });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-8 text-raven-text">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-raven-violet text-white">
            <ShieldCheck className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold">RavenTech OSINT</h1>
            <p className="text-sm text-raven-muted">Authorized intelligence workspace</p>
          </div>
        </div>

        <form
          onSubmit={(event) => void handleSubmit(event)}
          className="rounded-lg border border-raven-border bg-raven-panel/90 p-5 shadow-glow"
        >
          <label className="block text-sm text-raven-muted" htmlFor="identifier">
            Email or username
          </label>
          <input
            id="identifier"
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
            className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
            autoComplete="username"
            required
          />

          <label className="mt-4 block text-sm text-raven-muted" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
            autoComplete="current-password"
            required
          />

          {error ? (
            <div className="mt-4">
              <ErrorBlock message={error} />
            </div>
          ) : null}

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-5 w-full rounded-md bg-raven-violet px-4 py-2 font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Signing in" : "Sign in"}
          </button>
        </form>
      </div>
    </main>
  );
}
