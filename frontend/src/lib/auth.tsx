import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

import {
  ApiError,
  clearTokens,
  getAccessToken,
  getMe,
  login as loginRequest,
  logout as logoutRequest,
} from "./api";
import { AuthContext, type AuthContextValue } from "./auth-context";
import type { UserProfile } from "../types";

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isBootstrapping, setIsBootstrapping] = useState(true);

  useEffect(() => {
    let active = true;
    async function bootstrap(): Promise<void> {
      if (!getAccessToken()) {
        setIsBootstrapping(false);
        return;
      }
      try {
        const profile = await getMe();
        if (active) {
          setUser(profile);
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          clearTokens();
        }
      } finally {
        if (active) {
          setIsBootstrapping(false);
        }
      }
    }
    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (identifier: string, password: string) => {
    await loginRequest(identifier, password);
    const profile = await getMe();
    setUser(profile);
  }, []);

  const logout = useCallback(async () => {
    await logoutRequest();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: user !== null,
      isBootstrapping,
      login,
      logout,
    }),
    [isBootstrapping, login, logout, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
