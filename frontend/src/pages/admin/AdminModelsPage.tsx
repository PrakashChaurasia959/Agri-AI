import { AlertTriangle, CheckCircle2, Cpu, Database, FolderOpen } from 'lucide-react';

import { PageContainer, PageHeader } from '@/components/layout/AppLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { SkeletonRows } from '@/components/ui/Spinner';
import { ErrorState } from '@/components/ui/States';
import { useAsync } from '@/hooks/useAsync';
import { adminService } from '@/services';
import { formatMetric, formatPercent, scalarMetrics } from '@/utils/format';

export function AdminModelsPage() {
  const models = useAsync(() => adminService.models(), []);

  const payload = models.data;

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Administration"
        title="Models and services"
        description="Which machine-learning artifacts are installed on this server, what they scored on their held-out test split, and where they live on disk."
      />

      {models.error ? (
        <ErrorState
          title="The model status could not be loaded"
          description={models.error}
          onRetry={models.reload}
        />
      ) : null}

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="flex items-center gap-4 pt-5">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-500/12 text-brand-600 dark:text-brand-400">
              <Cpu className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Installed</p>
              <p className="font-display text-xl font-bold">
                {payload?.available_count ?? 0} / {payload?.total_count ?? 0}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 pt-5">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-earth-500/12 text-earth-600 dark:text-earth-400">
              <FolderOpen className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground">Artifact directory</p>
              <p className="truncate font-mono text-xs font-semibold">
                {payload?.model_dir ?? '—'}
              </p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 pt-5">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-sky-500/12 text-sky-600 dark:text-sky-400">
              <Database className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Compute device</p>
              <p className="font-display text-xl font-bold">{payload?.device ?? '—'}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {models.isLoading ? (
        <Card>
          <CardContent className="pt-6">
            <SkeletonRows rows={5} />
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {(payload?.models ?? []).map((model) => (
            <Card key={model.key}>
              <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
                <div>
                  <CardTitle>{model.display_name}</CardTitle>
                  <CardDescription className="mt-1">
                    {model.task.replace(/_/g, ' ')}
                    {model.classes_count ? ` · ${model.classes_count} classes` : ''}
                  </CardDescription>
                </div>
                <Badge
                  tone={model.available ? 'success' : 'warning'}
                  icon={
                    model.available ? (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    ) : (
                      <AlertTriangle className="h-3.5 w-3.5" />
                    )
                  }
                >
                  {model.available ? 'Installed' : 'Not installed'}
                </Badge>
              </CardHeader>
              <CardContent className="space-y-4">
                {model.available ? (
                  <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <div className="rounded-xl border border-border p-3">
                      <dt className="text-xs text-muted-foreground">Model</dt>
                      <dd className="truncate text-sm font-semibold">
                        {model.model_name ?? '—'}
                      </dd>
                      <dd className="text-xs text-muted-foreground">
                        v{model.model_version ?? '—'}
                      </dd>
                    </div>
                    <div className="rounded-xl border border-border p-3">
                      <dt className="text-xs text-muted-foreground">Accuracy</dt>
                      <dd className="font-display text-lg font-semibold">
                        {model.accuracy === null ? '—' : formatPercent(model.accuracy)}
                      </dd>
                    </div>
                    <div className="rounded-xl border border-border p-3">
                      <dt className="text-xs text-muted-foreground">Dataset</dt>
                      <dd className="truncate text-sm font-semibold">
                        {model.dataset ?? '—'}
                      </dd>
                    </div>
                    <div className="rounded-xl border border-border p-3">
                      <dt className="text-xs text-muted-foreground">Trained at</dt>
                      <dd className="text-sm font-semibold">{model.trained_at ?? '—'}</dd>
                    </div>
                  </dl>
                ) : (
                  <p className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-sm text-muted-foreground">
                    {model.message ??
                      'The artifact has not been installed on this server.'}
                  </p>
                )}

                {(() => {
                  const metrics = scalarMetrics(model.metrics);
                  if (!metrics.length) return null;
                  return (
                    <div>
                      <h4 className="mb-2 text-sm font-semibold">Measured metrics</h4>
                      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                        {metrics.map(([key, value]) => (
                          <div key={key} className="rounded-xl border border-border p-3">
                            <dt className="truncate text-xs capitalize text-muted-foreground">
                              {key.replace(/_/g, ' ')}
                            </dt>
                            <dd className="font-display text-base font-semibold">
                              {formatMetric(value, 4)}
                            </dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  );
                })()}

                {model.artifact_path ? (
                  <p className="truncate font-mono text-xs text-muted-foreground">
                    {model.artifact_path}
                  </p>
                ) : null}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {payload?.note ? (
        <p className="mt-6 text-xs text-muted-foreground">{payload.note}</p>
      ) : null}
    </PageContainer>
  );
}
