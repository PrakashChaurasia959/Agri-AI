import { Link } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  Bug,
  CheckCircle2,
  Leaf,
  Plus,
  Sprout,
  TrendingUp,
} from 'lucide-react';

import { PageContainer, PageHeader } from '@/components/layout/AppLayout';
import { StatCard } from '@/components/ui/StatCard';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Alert } from '@/components/ui/Alert';
import { SkeletonCard, SkeletonRows } from '@/components/ui/Spinner';
import { EmptyState, ErrorState } from '@/components/ui/States';
import {
  CropDistributionChart,
  DailyActivityChart,
  PredictionTypeChart,
} from '@/components/charts/Charts';
import { useAsync } from '@/hooks/useAsync';
import { dashboardService } from '@/services';
import { useAuth } from '@/contexts/AuthContext';
import { formatDateTime, formatPercent, relativeTime } from '@/utils/format';

export function DashboardPage() {
  const { user } = useAuth();
  const overview = useAsync(() => dashboardService.overview(), []);
  const analytics = useAsync(() => dashboardService.analytics(30), []);

  const counters = overview.data?.overview;

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Dashboard"
        title={`Welcome back, ${user?.name?.split(' ')[0] ?? 'farmer'}`}
        description="Everything you have run through AgriVision AI, summarised from your own records."
        actions={
          <>
            <Link
              to="/disease"
              className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border px-4 text-sm font-medium transition hover:bg-muted"
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              New analysis
            </Link>
            <Link
              to="/crops"
              className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700"
            >
              <Sprout className="h-4 w-4" aria-hidden="true" />
              Recommend a crop
            </Link>
          </>
        }
      />

      {overview.data && !overview.data.database_connected ? (
        <Alert tone="warning" className="mb-6" title="The database is not connected">
          Your predictions cannot be stored on this server right now, so the counters
          below may be empty even if you have used the tools before. Set{' '}
          <code className="font-mono">MONGODB_URI</code> and restart the API.
        </Alert>
      ) : null}

      {overview.error ? (
        <ErrorState
          title="We could not load your dashboard"
          description={overview.error}
          onRetry={overview.reload}
        />
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {overview.isLoading
          ? Array.from({ length: 4 }).map((_, index) => <SkeletonCard key={index} />)
          : (
            <>
              <StatCard
                label="Total predictions"
                value={counters?.total_predictions ?? 0}
                icon={Activity}
                hint="All analysis runs"
              />
              <StatCard
                label="Diseases detected"
                value={counters?.disease_predictions ?? 0}
                icon={Bug}
                tone="warning"
                hint={`${counters?.affected_leaves ?? 0} affected leaves`}
              />
              <StatCard
                label="Crop recommendations"
                value={counters?.crop_recommendations ?? 0}
                icon={Sprout}
                tone="earth"
                hint={`${counters?.distinct_crops_recommended ?? 0} distinct crops`}
              />
              <StatCard
                label="Yield estimates"
                value={counters?.yield_predictions ?? 0}
                icon={TrendingUp}
                tone="info"
                hint={`${counters?.saved_reports ?? 0} saved reports`}
              />
            </>
          )}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Predictions per day</CardTitle>
            <CardDescription>
              The last {analytics.data?.window_days ?? 30} days of activity on your account.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {analytics.isLoading ? (
              <SkeletonRows rows={5} />
            ) : analytics.error ? (
              <ErrorState description={analytics.error} onRetry={analytics.reload} />
            ) : (
              <DailyActivityChart
                data={(analytics.data?.daily_predictions ?? []).map((point) => ({
                  date: point.date.slice(5),
                  value: point.value,
                }))}
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Prediction mix</CardTitle>
            <CardDescription>How you split your analysis across the tools.</CardDescription>
          </CardHeader>
          <CardContent>
            {analytics.isLoading ? (
              <SkeletonRows rows={3} />
            ) : (
              <PredictionTypeChart
                data={(analytics.data?.prediction_type_breakdown ?? []).map((item) => ({
                  prediction_type: item.label,
                  count: item.value,
                }))}
              />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Most recommended crops</CardTitle>
            <CardDescription>Ranked from your own crop recommendation history.</CardDescription>
          </CardHeader>
          <CardContent>
            {analytics.isLoading ? (
              <SkeletonRows rows={4} />
            ) : (analytics.data?.crop_distribution ?? []).length === 0 ? (
              <EmptyState
                icon={<Sprout className="h-6 w-6" />}
                title="No crop recommendations yet"
                description="Run a crop recommendation with your soil and climate readings to see the ranking here."
                action={
                  <Link
                    to="/crops"
                    className="focus-ring inline-flex h-10 items-center justify-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white transition hover:bg-brand-700"
                  >
                    Recommend a crop
                  </Link>
                }
              />
            ) : (
              <CropDistributionChart
                data={(analytics.data?.crop_distribution ?? []).map((item) => ({
                  crop: item.crop,
                  count: item.value,
                  average_confidence: 0,
                }))}
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Confidence distribution</CardTitle>
            <CardDescription>How certain the models were.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(analytics.data?.confidence_buckets ?? []).map((bucket) => (
              <div
                key={bucket.label}
                className="flex items-center justify-between rounded-xl border border-border p-3"
              >
                <span className="text-sm text-muted-foreground">{bucket.label}</span>
                <span className="font-display text-lg font-semibold">{bucket.value}</span>
              </div>
            ))}
            {(analytics.data?.confidence_buckets ?? []).length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No predictions to summarise yet.
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader className="flex-row items-center justify-between gap-4 space-y-0">
          <div>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>Your eight most recent predictions.</CardDescription>
          </div>
          <Link
            to="/history"
            className="focus-ring inline-flex items-center gap-1 rounded text-sm font-medium text-brand-700 hover:underline dark:text-brand-400"
          >
            View all
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </CardHeader>
        <CardContent>
          {overview.isLoading ? (
            <SkeletonRows rows={5} />
          ) : (overview.data?.recent_predictions ?? []).length === 0 ? (
            <EmptyState
              icon={<Leaf className="h-6 w-6" />}
              title="Nothing here yet"
              description="Upload a leaf photo or run a crop recommendation to start building your farm record."
              action={
                <Link
                  to="/disease"
                  className="focus-ring inline-flex h-10 items-center justify-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white transition hover:bg-brand-700"
                >
                  Detect a disease
                </Link>
              }
            />
          ) : (
            <ul className="divide-y divide-border">
              {(overview.data?.recent_predictions ?? []).map((item) => (
                <li key={item.id} className="flex items-center gap-4 py-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                    {item.prediction_type === 'disease' ? (
                      <Leaf className="h-4 w-4 text-brand-600" aria-hidden="true" />
                    ) : item.prediction_type === 'crop_recommendation' ? (
                      <Sprout className="h-4 w-4 text-earth-600" aria-hidden="true" />
                    ) : (
                      <TrendingUp className="h-4 w-4 text-sky-600" aria-hidden="true" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium capitalize">
                      {item.predicted_class.replace(/_/g, ' ')}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {item.prediction_type.replace(/_/g, ' ')} ·{' '}
                      {relativeTime(item.created_at)}
                    </p>
                  </div>
                  <div className="hidden items-center gap-2 sm:flex">
                    {item.confidence !== null ? (
                      <Badge tone={item.confidence >= 0.8 ? 'success' : 'neutral'}>
                        {formatPercent(item.confidence)}
                      </Badge>
                    ) : (
                      <Badge tone="neutral">estimate</Badge>
                    )}
                  </div>
                  <span className="hidden text-xs text-muted-foreground md:block">
                    {formatDateTime(item.created_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {counters && counters.total_predictions > 0 ? (
        <p className="mt-6 flex items-center gap-2 text-xs text-muted-foreground">
          <CheckCircle2 className="h-3.5 w-3.5 text-brand-600" aria-hidden="true" />
          First prediction {formatDateTime(counters.first_prediction_at)} · most recent{' '}
          {formatDateTime(counters.last_prediction_at)}
        </p>
      ) : null}
    </PageContainer>
  );
}
