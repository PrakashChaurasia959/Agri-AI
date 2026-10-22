import { Sprout } from 'lucide-react';

import { Badge } from '@/components/ui/Badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { Alert } from '@/components/ui/Alert';
import { formatMetric } from '@/utils/format';
import type { CropRecommendation } from '@/types';

export function CropResultCard({ result }: { result: CropRecommendation }) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Best match
            </p>
            <CardTitle className="capitalize">
              {result.top_crop ?? 'No recommendation'}
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Match score{' '}
              {result.top_score === null ? '—' : `${(result.top_score * 100).toFixed(1)}%`}
            </p>
          </div>
          <Badge tone="brand" icon={<Sprout className="h-3.5 w-3.5" />}>
            {result.recommendations.length} suggestions
          </Badge>
        </CardHeader>
        <CardContent className="space-y-5">
          <ol className="space-y-3">
            {result.recommendations.map((item) => (
              <li key={item.crop} className="space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2 font-medium capitalize">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-500/12 text-xs font-semibold text-brand-700 dark:text-brand-300">
                      {item.rank}
                    </span>
                    {item.crop}
                  </span>
                  <span className="text-muted-foreground">
                    {(item.score * 100).toFixed(1)}%
                  </span>
                </div>
                <ProgressBar
                  value={item.score}
                  tone={item.rank === 1 ? 'brand' : 'earth'}
                />
              </li>
            ))}
          </ol>

          <div className="rounded-xl border border-border bg-muted/40 p-4">
            <h4 className="text-sm font-semibold">Why this crop</h4>
            {result.explanation.length ? (
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                {result.explanation.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground">
                The model did not attach an explanation to this result.
              </p>
            )}
          </div>

          {Object.keys(result.metrics).length ? (
            <div>
              <h4 className="mb-2 text-sm font-semibold">Model metrics</h4>
              <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {Object.entries(result.metrics).map(([key, value]) => (
                  <div key={key} className="rounded-xl border border-border p-3">
                    <dt className="truncate text-xs capitalize text-muted-foreground">
                      {key.replace(/_/g, ' ')}
                    </dt>
                    <dd className="font-display text-lg font-semibold">
                      {formatMetric(value, 4)}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          ) : null}

          <p className="text-xs text-muted-foreground">
            Model: {result.model_name} v{result.model_version}
          </p>
        </CardContent>
      </Card>

      <Alert tone="info" title="Agronomic disclaimer">
        {result.disclaimer}
      </Alert>
    </div>
  );
}
