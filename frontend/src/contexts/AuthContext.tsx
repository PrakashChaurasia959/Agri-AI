/**
 * Authentication context.
 *
 * The session lives in an HttpOnly cookie, so the *only* thing the browser
 * can do is ask the backend "who am I?".  The context keeps the resulting
 * user object in memory and re-validates it on mount.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import { authService } from '@/services/auth';
import { ApiError } from '@/services/api';
import type { LoginPayload, RegisterPayload, User } from '@/types';

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  error: string | null;
  login: (payload: LoginPayload) => Promise<User>;
  register: (payload: RegisterPayload) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<User | null>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const refreshUser = useCallback(async (): Promise<User | null> => {
    try {
      const current = await authService.me();
      if (mounted.current) setUser(current);
      return current;
    } catch (caught) {
      // A 401 simply means "not signed in" - that is not an error worth
      // showing to the user.  Anything else (a 503 because MongoDB is down)
      // is worth surfacing.
      if (caught instanceof ApiError && caught.isUnauthorized) {
        if (mounted.current) setUser(null);
        return null;
      }
      if (caught instanceof ApiError && caught.isDatabaseUnavailable) {
        if (mounted.current) {
          setUser(null);
          setError(
            'The database is unreachable, so your profile cannot be loaded. Please try again shortly.',
          );
        }
        return null;
      }
      if (mounted.current) setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await refreshUser();
      if (!cancelled && mounted.current) setIsLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshUser]);

  const login = useCallback(async (payload: LoginPayload): Promise<User> => {
    setError(null);
    try {
      const response = await authService.login(payload);
      if (mounted.current) setUser(response.user);
      return response.user;
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : 'Unable to sign in right now.';
      if (mounted.current) setError(message);
      throw caught;
    }
  }, []);

  const register = useCallback(async (payload: RegisterPayload): Promise<User> => {
    setError(null);
    try {
      const response = await authService.register(payload);
      if (mounted.current) setUser(response.user);
      return response.user;
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : 'Unable to create the account.';
      if (mounted.current) setError(message);
      throw caught;
    }
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    try {
      await authService.logout();
    } catch {
      // Even if the server call fails the local session must be dropped.
    } finally {
      if (mounted.current) setUser(null);
    }
  }, []);

  const clearError = useCallback(() => {
    if (mounted.current) setError(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: user !== null,
      isAdmin: user?.role === 'admin',
      error,
      login,
      register,
      logout,
      refreshUser,
      clearError,
    }),
    [user, isLoading, error, login, register, logout, refreshUser, clearError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside an <AuthProvider>.');
  }
  return context;
}
