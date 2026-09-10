import { ShieldCheck, UserPlus } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import {
  ApiError,
  getRegistrationPolicy,
  registerAccount,
} from "../lib/api";
import { safeInternalRoute } from "../lib/safe";
import { useAuth } from "../lib/useAuth";
import type { RegistrationPolicyResponse } from "../types";
import { LanguageSwitcher } from "../components/LanguageSwitcher";

interface LocationState {
  from?: { pathname?: string };
}

export function LoginPage(): JSX.Element {
  const { isAuthenticated, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as LocationState | null;
  const [mode, setMode] = useState<"login" | "register">("login");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [registerUsername, setRegisterUsername] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerFullName, setRegisterFullName] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [registerConfirmPassword, setRegisterConfirmPassword] = useState("");
  const [registerInviteCode, setRegisterInviteCode] = useState("");
  const [policy, setPolicy] = useState<RegistrationPolicyResponse | null>(null);
  const [policyError, setPolicyError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);

  useEffect(() => {
    let active = true;
    getRegistrationPolicy()
      .then((response) => {
        if (active) {
          setPolicy(response);
          setPolicyError(null);
        }
      })
      .catch(() => {
        if (active) {
          setPolicyError(
            "Registration policy could not be loaded. Sign-in still works.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      await login(identifier, password);
      navigate(safeInternalRoute(state?.from?.pathname), { replace: true });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Login failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleRegister(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    if (registerPassword !== registerConfirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (policy && !policy.public_registration_enabled) {
      setError("Public registration is currently disabled.");
      return;
    }
    setIsRegistering(true);
    try {
      const response = await registerAccount({
        username: registerUsername,
        email: registerEmail,
        full_name: registerFullName || undefined,
        password: registerPassword,
        invite_code: registerInviteCode || undefined,
      });
      setSuccess(response.message);
      setMode("login");
      setIdentifier(response.email);
      setRegisterUsername("");
      setRegisterEmail("");
      setRegisterFullName("");
      setRegisterInviteCode("");
    } catch (caught) {
      setError(cleanRegistrationError(caught));
    } finally {
      setRegisterPassword("");
      setRegisterConfirmPassword("");
      setIsRegistering(false);
    }
  }

  function showRegister(): void {
    setMode("register");
    setError(null);
    setSuccess(null);
  }

  function showLogin(): void {
    setMode("login");
    setError(null);
  }

  const registerDisabled = policy?.public_registration_enabled === false;
  const registerReady =
    registerUsername.trim().length >= 2 &&
    registerEmail.trim().length > 3 &&
    registerPassword.length > 0 &&
    registerConfirmPassword.length > 0 &&
    registerPassword === registerConfirmPassword &&
    (!policy?.invite_code_required || registerInviteCode.trim().length > 0) &&
    !registerDisabled &&
    !isRegistering;

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-8 text-raven-text">
      <div className="w-full max-w-md">
        <div className="mb-4 flex justify-end"><LanguageSwitcher /></div>
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-raven-violet text-white">
            <ShieldCheck className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold">RavenTech OSINT</h1>
            <p className="text-sm text-raven-muted">
              Defensive Intelligence &amp; Threat Investigation Workspace
            </p>
          </div>
        </div>

        <div className="rounded-lg border border-raven-border bg-raven-panel/90 p-5 shadow-glow">
          {mode === "login" ? (
            <form onSubmit={(event) => void handleSubmit(event)}>
              <label
                className="block text-sm text-raven-muted"
                htmlFor="identifier"
              >
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

              <label
                className="mt-4 block text-sm text-raven-muted"
                htmlFor="password"
              >
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

              <MessageBlock error={error} success={success} />

              <button
                type="submit"
                disabled={isSubmitting}
                className="mt-5 w-full rounded-md bg-raven-violet px-4 py-2 font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? "Signing in" : "Sign in"}
              </button>
              <button
                type="button"
                onClick={showRegister}
                className="mt-3 flex w-full items-center justify-center gap-2 rounded-md border border-raven-border px-4 py-2 text-sm font-medium text-raven-text hover:border-raven-violet"
              >
                <UserPlus className="h-4 w-4" aria-hidden="true" />
                Create account
              </button>
              {policyError ? (
                <p className="mt-3 text-xs text-amber-200">{policyError}</p>
              ) : null}
            </form>
          ) : (
            <form onSubmit={(event) => void handleRegister(event)}>
              <div className="mb-4">
                <h2 className="text-lg font-semibold text-raven-text">
                  Create account
                </h2>
                <p className="mt-1 text-sm text-raven-muted">
                  Accounts are created with non-admin access and follow the
                  configured registration policy.
                </p>
              </div>

              {registerDisabled ? (
                <div className="mb-4 rounded-md border border-amber-400/30 bg-amber-500/10 p-3 text-sm text-amber-100">
                  Public registration is currently disabled. Ask an
                  administrator to create an account or enable registration.
                </div>
              ) : null}

              <label
                className="block text-sm text-raven-muted"
                htmlFor="register-username"
              >
                Username
              </label>
              <input
                id="register-username"
                value={registerUsername}
                onChange={(event) => setRegisterUsername(event.target.value)}
                className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
                autoComplete="username"
                required
              />

              <label
                className="mt-4 block text-sm text-raven-muted"
                htmlFor="register-email"
              >
                Email
              </label>
              <input
                id="register-email"
                type="email"
                value={registerEmail}
                onChange={(event) => setRegisterEmail(event.target.value)}
                className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
                autoComplete="email"
                required
              />

              <label
                className="mt-4 block text-sm text-raven-muted"
                htmlFor="register-full-name"
              >
                Full name
                <span className="text-raven-muted/70"> optional</span>
              </label>
              <input
                id="register-full-name"
                value={registerFullName}
                onChange={(event) => setRegisterFullName(event.target.value)}
                className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
                autoComplete="name"
              />

              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <label className="block text-sm text-raven-muted">
                  Password
                  <input
                    type="password"
                    value={registerPassword}
                    onChange={(event) => setRegisterPassword(event.target.value)}
                    className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
                    autoComplete="new-password"
                    required
                  />
                </label>
                <label className="block text-sm text-raven-muted">
                  Confirm password
                  <input
                    type="password"
                    value={registerConfirmPassword}
                    onChange={(event) =>
                      setRegisterConfirmPassword(event.target.value)
                    }
                    className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
                    autoComplete="new-password"
                    required
                  />
                </label>
              </div>
              <p className="mt-2 text-xs text-raven-muted">
                Use at least 12 characters with uppercase, lowercase, a digit,
                and a special character.
              </p>

              {policy?.invite_code_required ? (
                <label
                  className="mt-4 block text-sm text-raven-muted"
                  htmlFor="register-invite"
                >
                  Invite code
                  <input
                    id="register-invite"
                    type="password"
                    value={registerInviteCode}
                    onChange={(event) => setRegisterInviteCode(event.target.value)}
                    className="mt-2 w-full rounded-md border border-raven-border bg-raven-bg px-3 py-2 text-raven-text outline-none focus:border-raven-violet"
                    autoComplete="off"
                    required
                  />
                </label>
              ) : null}

              {policy?.requires_approval ? (
                <p className="mt-3 text-xs text-raven-muted">
                  New accounts require administrator approval before sign-in.
                </p>
              ) : null}

              <MessageBlock error={error} success={success} />

              <button
                type="submit"
                disabled={!registerReady}
                className="mt-5 w-full rounded-md bg-raven-violet px-4 py-2 font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isRegistering ? "Creating account" : "Create account"}
              </button>
              <button
                type="button"
                onClick={showLogin}
                className="mt-3 w-full rounded-md border border-raven-border px-4 py-2 text-sm font-medium text-raven-text hover:border-raven-violet"
              >
                Return to sign in
              </button>
            </form>
          )}
        </div>
      </div>
    </main>
  );
}

function MessageBlock({
  error,
  success,
}: {
  error: string | null;
  success: string | null;
}): JSX.Element | null {
  if (error) {
    return (
      <div className="mt-4 rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
        {error}
      </div>
    );
  }
  if (success) {
    return (
      <div className="mt-4 rounded-md border border-emerald-400/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
        {success}
      </div>
    );
  }
  return null;
}

function cleanRegistrationError(caught: unknown): string {
  if (caught instanceof ApiError) {
    return caught.metadata.detail || caught.message;
  }
  return caught instanceof Error ? caught.message : "Registration failed.";
}
