import { AlertTriangle, Bug, CheckCircle2, Clock, Leaf, ShieldAlert } from 'lucide-react';

import { Badge } from '@/components/ui/Badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { TopPredictionsChart } from '@/components/charts/Charts';
import { Alert } from '@/components/ui/Alert';
import { humaniseClassName } from '@/utils/format';
import type { DiseasePrediction, ImageMetadata } from '@/types';

function imageString(image: ImageMetadata, key: string): string | null {
  const value = image[key];
  if (value === null || value === undefined) return null;
  return String(value);
}

export function DiseaseResultCard({ result }: { result: DiseasePrediction }) {
  const info = result.disease_info;
  const healthy = result.is_healthy;
  const width = imageString(result.image, 'width');
  const height = imageString(result.image, 'height');
  const format = imageString(result.image, 'format');

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Diagnosis
            </p>
            <CardTitle>{result.display_name}</CardTitle>
            <p className="font-mono text-xs text-muted-foreground">{result.predicted_class}</p>
          </div>
          <Badge
            tone={healthy ? 'success' : 'danger'}
            icon={
              healthy ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : (
                <Bug className="h-3.5 w-3.5" />
              )
            }
          >
            {healthy ? 'Healthy' : 'Disease detected'}
          </Badge>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-border bg-muted/40 p-4">
              <p className="text-xs text-muted-foreground">Confidence</p>
              <p className="mt-1 font-display text-2xl font-bold">
                {result.confidence_percent.toFixed(1)}%
              </p>
            </div>
            <div className="rounded-xl border border-border bg-muted/40 p-4">
              <p className="text-xs text-muted-foreground">Inference time</p>
              <p className="mt-1 font-display text-2xl font-bold">
                {result.inference_ms.toFixed(0)}
                <span className="ml-1 text-sm font-medium text-muted-foreground">ms</span>
              </p>
            </div>
            <div className="rounded-xl border border-border bg-muted/40 p-4">
              <p className="text-xs text-muted-foreground">Model</p>
              <p className="mt-1 truncate font-display text-sm font-semibold">
                {result.model_name}
              </p>
              <p className="text-xs text-muted-foreground">v{result.model_version}</p>
            </div>
          </div>

          <ProgressBar
            value={result.confidence}
            label="Classification confidence"
            showValue
            tone={healthy ? 'brand' : 'warning'}
          />

          {!result.is_certain && result.uncertainty_message ? (
            <Alert tone="warning" title="Low confidence result">
              {result.uncertainty_message}
            </Alert>
          ) : null}

          <div>
            <h4 className="mb-2 text-sm font-semibold">Top predictions</h4>
            <TopPredictionsChart
              data={result.top_predictions.map((item) => ({
                label: humaniseClassName(item.label),
                probability: item.probability,
              }))}
            />
          </div>

          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div className="rounded-xl border border-border p-3">
              <dt className="text-xs text-muted-foreground">Crop</dt>
              <dd className="font-medium">{info?.crop ?? 'Not identified'}</dd>
            </div>
            <div className="rounded-xl border border-border p-3">
              <dt className="text-xs text-muted-foreground">Severity</dt>
              <dd className="font-medium capitalize">{info?.severity ?? 'Not rated'}</dd>
            </div>
            <div className="rounded-xl border border-border p-3">
              <dt className="text-xs text-muted-foreground">Image</dt>
              <dd className="font-medium">
                {width && height ? `${width} × ${height} px` : 'Not recorded'}
                {format ? ` · ${format}` : ''}
              </dd>
            </div>
            <div className="rounded-xl border border-border p-3">
              <dt className="text-xs text-muted-foreground">Saved to history</dt>
              <dd className="font-medium">{result.saved ? 'Yes' : 'No'}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {info && info.symptoms.length ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Leaf className="h-4 w-4 text-brand-600" aria-hidden="true" />
              Symptoms
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1.5 pl-5 text-sm text-muted-foreground">
              {info.symptoms.map((symptom) => (
                <li key={symptom}>{symptom}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {info && (info.prevention.length || info.treatment.length) ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {info.prevention.length ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <ShieldAlert className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                  Prevention
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc space-y-1.5 pl-5 text-sm text-muted-foreground">
                  {info.prevention.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}

          {info.treatment.length ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <AlertTriangle className="h-4 w-4 text-amber-600" aria-hidden="true" />
                  Treatment
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc space-y-1.5 pl-5 text-sm text-muted-foreground">
                  {info.treatment.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <p className="mt-4 rounded-lg bg-muted/60 p-3 text-xs text-muted-foreground">
                  Always confirm the product, dose and pre-harvest interval with your
                  local agricultural extension officer before applying anything.
                </p>
              </CardContent>
            </Card>
          ) : null}
        </div>
      ) : null}

      {info?.disclaimer ? (
        <Alert tone="info" title="Please note">
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            {info.disclaimer}
          </span>
        </Alert>
      ) : null}
    </div>
  );
}
