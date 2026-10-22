import type { ReactNode } from 'react';
import { TrendingDown, TrendingUp, type LucideIcon } from 'lucide-react';

import { cn } from '@/utils/cn';

export interface StatCardProps {
  label: string;
  value: ReactNode;
  icon?: LucideIcon;
  hint?: string;
  trend?: number | null;
  tone?: 'brand' | 'earth' | 'info' | 'warning';
  className?: string;
}

const TONES = {
  brand: 'bg-brand-500/12 text-brand-600 dark:text-brand-400',
  earth: 'bg-earth-500/12 text-earth-600 dark:text-earth-400',
  info: 'bg-sky-500/12 text-sky-600 dark:text-sky-400',
  warning: 'bg-amber-500/12 text-amber-600 dark:text-amber-400',
};

export function StatCard({
  label,
  value,
  icon: Icon,
  hint,
  trend,
  tone = 'brand',
  className,
}: StatCardProps) {
  const hasTrend = typeof trend === 'number' && Number.isFinite(trend);
  const rising = hasTrend && trend > 0;

  return (
    <div
      className={cn(
        'rounded-2xl border border-border bg-card p-5 shadow-soft transition hover:shadow-glow',
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm text-muted-foreground">{label}</p>
          <p className="mt-1 font-display text-2xl font-semibold tracking-tight">{value}</p>
        </div>
        {Icon ? (
          <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-xl', TONES[tone])}>
            <Icon className="h-5 w-5" aria-hidden="true" />
          </div>
        ) : null}
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs">
        {hasTrend ? (
          <span
            className={cn(
              'inline-flex items-center gap-0.5 font-medium',
              rising ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400',
            )}
          >
            {rising ? (
              <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <TrendingDown className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            {Math.abs(trend as number).toFixed(1)}%
          </span>
        ) : null}
        {hint ? <span className="text-muted-foreground">{hint}</span> : null}
      </div>
    </div>
  );
}
