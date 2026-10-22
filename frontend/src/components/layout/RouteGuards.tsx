import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';

import { useAuth } from '@/contexts/AuthContext';
import { Spinner } from '@/components/ui/Spinner';
import { ErrorState } from '@/components/ui/States';

/**
 * Gate for pages that need a signed-in user.
 *
 * While the session is being validated a spinner is shown - redirecting
 * before the answer arrives would bounce an authenticated user to the login
 * page on every refresh.
 */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading, error } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Spinner className="h-7 w-7" />
          <p className="text-sm text-muted-foreground">Checking your session…</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    // Remember where the user wanted to go so they can be sent back.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <ErrorState title="We could not verify your session" description={error} />
      </div>
    );
  }

  return <>{children}</>;
}

/** Gate for the administration area. */
export function AdminRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isAdmin, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Spinner className="h-7 w-7" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (!isAdmin) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <ErrorState
          title="Administrator access required"
          description="This area is restricted to administrator accounts. If you believe this is a mistake, contact the site owner."
        />
      </div>
    );
  }

  return <>{children}</>;
}

/** Keeps a signed-in user away from the login / register pages. */
export function PublicOnlyRoute({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Spinner className="h-7 w-7" />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
