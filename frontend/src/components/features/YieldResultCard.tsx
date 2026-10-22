import { Scale, TrendingUp } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Alert } from '@/components/ui/Alert';
import { formatMetric, formatNumber } from '@/utils/format';
import type { YieldPrediction } from '@/types';

export function YieldResultCard({ result }: { result: YieldPrediction }) {
  const areaHa =
    typeof result.input_summary?.area_ha === 'number' ? result.input_summary.area_ha : null;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="capitalize">Estimated yield for {result.crop_type}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-border bg-muted/40 p-4">
              <p className="flex items-center gap-1 text-xs text-muted-foreground">
                <Scale className="h-3.5 w-3.5" aria-hidden="true" />
                Total harvest
              </p>
              <p className="mt-1 font-display text-2xl font-bold">
                {result.estimated_yield === null
                  ? '—'
                  : formatNumber(result.estimated_yield)}
                <span className="ml-1 text-sm font-medium text-muted-foreground">t</span>
              </p>
            </div>
            <div className="rounded-xl border border-border bg-muted/40 p-4">
              <p className="flex items-center gap-1 text-xs text-muted-foreground">
                <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
                Per hectare
              </p>
              <p className="mt-1 font-display text-2xl font-bold">
                {result.per_hectare_yield === null
                  ? '—'
                  : formatNumber(result.per_hectare_yield)}
                <span className="ml-1 text-sm font-medium text-muted-foreground">t/ha</span>
              </p>
            </div>
            <div className="rounded-xl border border-border bg-muted/40 p-4">
              <p className="text-xs text-muted-foreground">Area</p>
              <p className="mt-1 font-display text-2xl font-bold">
                {areaHa === null ? '—' : formatNumber(areaHa)}
                <span className="ml-1 text-sm font-medium text-muted-foreground">ha</span>
              </p>
            </div>
          </div>

          {result.confidence_interval ? (
            <div className="rounded-xl border border-border p-4">
              <p className="text-xs text-muted-foreground">Expected range (tonnes)</p>
              <p className="mt-1 font-display text-lg font-semibold">
                {formatNumber(result.confidence_interval[0])} –{' '}
                {formatNumber(result.confidence_interval[1])} t
              </p>
            </div>
          ) : null}

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
            Model: {result.model_name} v{result.model_version} · unit: {result.yield_unit}
          </p>
        </CardContent>
      </Card>

      <Alert tone="info" title="Planning disclaimer">
        {result.disclaimer}
      </Alert>
    </div>
  );
}
