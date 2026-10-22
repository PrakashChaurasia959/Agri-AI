import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '@/utils/cn';

type Tone = 'neutral' | 'brand' | 'earth' | 'success' | 'warning' | 'danger' | 'info';

const TONES: Record<Tone, string> = {
  neutral: 'bg-muted text-muted-foreground border-border',
  brand: 'bg-brand-500/12 text-brand-700 border-brand-500/30 dark:text-brand-300',
  earth: 'bg-earth-500/12 text-earth-700 border-earth-500/30 dark:text-earth-300',
  success: 'bg-emerald-500/12 text-emerald-700 border-emerald-500/30 dark:text-emerald-300',
  warning: 'bg-amber-500/12 text-amber-700 border-amber-500/30 dark:text-amber-300',
  danger: 'bg-red-500/12 text-red-700 border-red-500/30 dark:text-red-300',
  info: 'bg-sky-500/12 text-sky-700 border-sky-500/30 dark:text-sky-300',
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
  icon?: ReactNode;
}

export function Badge({ tone = 'neutral', icon, className, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        TONES[tone],
        className,
      )}
      {...props}
    >
      {icon}
      {children}
    </span>
  );
}
