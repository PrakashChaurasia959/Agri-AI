import { Activity, Bug, Sprout, TrendingUp, Users } from 'lucide-react';

import { PageContainer, PageHeader } from '@/components/layout/AppLayout';
import { StatCard } from '@/components/ui/StatCard';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { SkeletonCard, SkeletonRows } from '@/components/ui/Spinner';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { PredictionTypeChart } from '@/components/charts/Charts';
import { useAsync } from '@/hooks/useAsync';
import { adminService } from '@/services';

export function AdminStatsPage() {
  const stats = useAsync(() => adminService.stats(), []);
  const analytics = useAsync(() => adminService.analytics(), []);

  const counters = stats.data;

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Administration"
        title="Platform statistics"
        description="Counters computed directly from the MongoDB collections - no cached or sampled numbers."
      />

      {stats.error ? (
        <ErrorState
          title="The statistics could not be loaded"
          description={stats.error}
          onRetry={stats.reload}
        />
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.isLoading
          ? Array.from({ length: 4 }).map((_, index) => <SkeletonCard key={index} />)
          : (
            <>
              <StatCard
                label="Registered users"
                value={counters?.total_users ?? 0}
                icon={Users}
                hint={`${counters?.new_users_7d ?? 0} joined in the last 7 days`}
              />
              <StatCard
                label="Total predictions"
                value={counters?.total_predictions ?? 0}
                icon={Activity}
                tone="earth"
                hint={`${counters?.predictions_7d ?? 0} in the last 7 days`}
              />
              <StatCard
                label="Disease analyses"
                value={counters?.disease_predictions ?? 0}
                icon={Bug}
                tone="warning"
                hint={`${counters?.affected_leaves ?? 0} affected leaves`}
              />
              <StatCard
                label="Crop recommendations"
                value={counters?.crop_recommendations ?? 0}
                icon={Sprout}
                tone="info"
                hint={`${counters?.yield_predictions ?? 0} yield estimates`}
              />
            </>
          )}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Predictions by type</CardTitle>
            <CardDescription>Across every account on the platform.</CardDescription>
          </CardHeader>
          <CardContent>
            {analytics.isLoading ? (
              <SkeletonRows rows={4} />
            ) : analytics.error ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                {analytics.error}
              </p>
            ) : (analytics.data?.prediction_type_breakdown ?? []).length === 0 ? (
              <EmptyState
                icon={<TrendingUp className="h-6 w-6" />}
                title="No predictions recorded"
                description="Once users start running the tools the breakdown appears here."
              />
            ) : (
              <PredictionTypeChart
                data={(analytics.data?.prediction_type_breakdown ?? []).map((item) => ({
                  prediction_type: (item.type ?? 'unknown').replace(/_/g, ' '),
                  count: item.value,
                }))}
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Most detected classes</CardTitle>
            <CardDescription>
              {analytics.data?.distinct_classes ?? 0} distinct disease classes have been
              predicted on this platform.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {analytics.isLoading ? (
              <SkeletonRows rows={5} />
            ) : (analytics.data?.top_disease_classes ?? []).length === 0 ? (
              <EmptyState
                icon={<Bug className="h-6 w-6" />}
                title="Nothing to rank yet"
                description="No disease has been detected on this platform so far."
              />
            ) : (
              <ul className="space-y-2">
                {(analytics.data?.top_disease_classes ?? []).map((entry) => (
                  <li
                    key={entry.label}
                    className="flex items-center justify-between rounded-xl border border-border px-3 py-2"
                  >
                    <span className="truncate font-mono text-xs">{entry.label}</span>
                    <span className="ml-3 shrink-0 font-display text-sm font-semibold">
                      {entry.count}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </PageContainer>
  );
}
