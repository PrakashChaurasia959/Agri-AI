import { Link } from 'react-router-dom';
import { Compass, Home } from 'lucide-react';

import { PageContainer } from '@/components/layout/AppLayout';

export function NotFoundPage() {
  return (
    <PageContainer>
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-500/12 text-brand-600 dark:text-brand-400">
          <Compass className="h-8 w-8" aria-hidden="true" />
        </div>
        <div className="space-y-2">
          <p className="font-display text-5xl font-bold tracking-tight">404</p>
          <h1 className="font-display text-xl font-semibold">This page does not exist</h1>
          <p className="mx-auto max-w-md text-sm text-muted-foreground">
            The link may be out of date, or the page may have been moved. Head back to
            the dashboard to keep working.
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/dashboard"
            className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700"
          >
            <Home className="h-4 w-4" aria-hidden="true" />
            Go to the dashboard
          </Link>
          <Link
            to="/"
            className="focus-ring inline-flex h-10 items-center justify-center rounded-lg border border-border px-4 text-sm font-medium transition hover:bg-muted"
          >
            Landing page
          </Link>
        </div>
      </div>
    </PageContainer>
  );
}
