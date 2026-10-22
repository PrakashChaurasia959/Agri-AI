import { cn } from '@/utils/cn';

export interface ProgressBarProps {
  value: number;
  max?: number;
  tone?: 'brand' | 'earth' | 'warning' | 'danger';
  label?: string;
  showValue?: boolean;
  className?: string;
}

const TONES = {
  brand: 'bg-brand-500',
  earth: 'bg-earth-500',
  warning: 'bg-amber-500',
  danger: 'bg-red-500',
};

export function ProgressBar({
  value,
  max = 1,
  tone = 'brand',
  label,
  showValue = false,
  className,
}: ProgressBarProps) {
  const percent = max === 0 ? 0 : Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className={cn('space-y-1.5', className)}>
      {label || showValue ? (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          {label ? <span>{label}</span> : <span />}
          {showValue ? <span className="font-medium text-foreground">{percent.toFixed(1)}%</span> : null}
        </div>
      ) : null}
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={Math.round(percent)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? 'Progress'}
      >
        <div
          className={cn('h-full rounded-full transition-[width] duration-500', TONES[tone])}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
