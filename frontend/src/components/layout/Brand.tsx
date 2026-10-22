import { Link } from 'react-router-dom';
import { Sprout } from 'lucide-react';

import { cn } from '@/utils/cn';

export function Brand({
  className,
  compact = false,
}: {
  className?: string;
  compact?: boolean;
}) {
  return (
    <Link
      to="/"
      className={cn(
        'focus-ring inline-flex items-center gap-2.5 rounded-lg font-display text-lg font-bold tracking-tight',
        className,
      )}
    >
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 text-white shadow-sm">
        <Sprout className="h-5 w-5" aria-hidden="true" />
      </span>
      {compact ? null : (
        <span className="gradient-text">
          AgriVision <span className="text-foreground/70">AI</span>
        </span>
      )}
    </Link>
  );
}
