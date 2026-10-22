import type { ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, Info, TriangleAlert } from 'lucide-react';

import { cn } from '@/utils/cn';

type Tone = 'info' | 'success' | 'warning' | 'danger';

const TONES: Record<Tone, { wrapper: string; icon: typeof Info }> = {
  info: {
    wrapper: 'border-sky-500/30 bg-sky-500/5 text-sky-800 dark:text-sky-200',
    icon: Info,
  },
  success: {
    wrapper: 'border-emerald-500/30 bg-emerald-500/5 text-emerald-800 dark:text-emerald-200',
    icon: CheckCircle2,
  },
  warning: {
    wrapper: 'border-amber-500/30 bg-amber-500/5 text-amber-800 dark:text-amber-200',
    icon: TriangleAlert,
  },
  danger: {
    wrapper: 'border-red-500/30 bg-red-500/5 text-red-800 dark:text-red-200',
    icon: AlertTriangle,
  },
};

export interface AlertProps {
  tone?: Tone;
  title?: string;
  children?: ReactNode;
  className?: string;
  onDismiss?: () => void;
}

export function Alert({ tone = 'info', title, children, className, onDismiss }: AlertProps) {
  const { wrapper, icon: Icon } = TONES[tone];
  return (
    <div
      role="alert"
      className={cn('flex items-start gap-3 rounded-xl border p-4 text-sm', wrapper, className)}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1 space-y-1">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className="leading-relaxed opacity-90">{children}</div> : null}
      </div>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded-md px-1 text-xs font-medium opacity-70 transition hover:opacity-100"
        >
          Dismiss
        </button>
      ) : null}
    </div>
  );
}
