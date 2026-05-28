import { createContext } from "react";

import type { UserProfile } from "../types";

export interface AuthContextValue {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isBootstrapping: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

