import type { ReactNode } from 'react';
import { AlertTriangle, DatabaseZap, Inbox, RefreshCw, ServerCrash } from 'lucide-react';

import { Button } from './Button';
import { cn } from '@/utils/cn';

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-card/50 px-6 py-14 text-center',
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
        {icon ?? <Inbox className="h-6 w-6" aria-hidden="true" />}
      </div>
      <div className="space-y-1">
        <p className="font-display text-base font-semibold">{title}</p>
        {description ? (
          <p className="mx-auto max-w-md text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export interface ErrorStateProps {
  title?: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  title = 'Something went wrong',
  description,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-2xl border border-red-500/30 bg-red-500/5 px-6 py-12 text-center',
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-500/12 text-red-600 dark:text-red-400">
        <AlertTriangle className="h-6 w-6" aria-hidden="true" />
      </div>
      <div className="space-y-1">
        <p className="font-display text-base font-semibold text-red-700 dark:text-red-300">
          {title}
        </p>
        {description ? (
          <p className="mx-auto max-w-lg text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Try again
        </Button>
      ) : null}
    </div>
  );
}

/**
 * A specific message for the "the server has no database" case, which is a
 * deployment problem rather than a user error.
 */
export function DatabaseUnavailableState({ onRetry }: { onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/5 px-6 py-12 text-center"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/12 text-amber-600 dark:text-amber-400">
        <DatabaseZap className="h-6 w-6" aria-hidden="true" />
      </div>
      <div className="space-y-1">
        <p className="font-display text-base font-semibold text-amber-700 dark:text-amber-300">
          The database is not connected
        </p>
        <p className="mx-auto max-w-lg text-sm text-muted-foreground">
          This server has no MongoDB connection configured, so records cannot be read or
          written. Set <code className="font-mono">MONGODB_URI</code> in{' '}
          <code className="font-mono">backend/.env</code> and restart the API.
        </p>
      </div>
      {onRetry ? (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Check again
        </Button>
      ) : null}
    </div>
  );
}

/** A specific message for the "the model is not installed" case. */
export function ModelUnavailableState({
  modelName,
  trainCommand,
}: {
  modelName: string;
  trainCommand: string;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/5 px-6 py-12 text-center"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/12 text-amber-600 dark:text-amber-400">
        <ServerCrash className="h-6 w-6" aria-hidden="true" />
      </div>
      <div className="space-y-1">
        <p className="font-display text-base font-semibold text-amber-700 dark:text-amber-300">
          {modelName} is not available on this server
        </p>
        <p className="mx-auto max-w-lg text-sm text-muted-foreground">
          The trained model artifact has not been installed, so the API refuses to
          return a result rather than inventing one. Train and install it with:
        </p>
        <code className="mt-2 inline-block rounded-lg bg-muted px-3 py-1.5 font-mono text-xs text-foreground">
          {trainCommand}
        </code>
      </div>
    </div>
  );
}
