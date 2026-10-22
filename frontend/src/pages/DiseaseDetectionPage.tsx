import { useState } from 'react';
import { AlertTriangle, Leaf, Loader2, Scan } from 'lucide-react';

import { PageContainer, PageHeader } from '@/components/layout/AppLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Alert } from '@/components/ui/Alert';
import { ImageDropzone } from '@/components/features/ImageDropzone';
import { DiseaseResultCard } from '@/components/features/DiseaseResultCard';
import { ModelUnavailableState } from '@/components/ui/States';
import { useToast } from '@/contexts/ToastContext';
import { diseaseService } from '@/services/disease';
import { ApiError } from '@/services/api';
import type { DiseasePrediction } from '@/types';

const MODEL_UNAVAILABLE_HINT =
  'cd backend && python -m ml.train_cnn --epochs 6 --batch-size 64';

export function DiseaseDetectionPage() {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<DiseasePrediction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modelUnavailable, setModelUnavailable] = useState(false);
  const [isPredicting, setIsPredicting] = useState(false);

  const runPrediction = async () => {
    if (!file) return;
    setIsPredicting(true);
    setError(null);
    setModelUnavailable(false);
    try {
      const prediction = await diseaseService.predict(file);
      setResult(prediction);
      toast.success(
        prediction.is_healthy ? 'The leaf looks healthy.' : 'A disease was detected.',
        `${prediction.display_name} · ${prediction.confidence_percent.toFixed(1)}% confidence`,
      );
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 503) {
        setModelUnavailable(true);
        setResult(null);
      } else {
        const message =
          caught instanceof Error ? caught.message : 'The analysis could not be completed.';
        setError(message);
        toast.error('Analysis failed', message);
      }
    } finally {
      setIsPredicting(false);
    }
  };

  const reset = () => {
    setFile(null);
    setResult(null);
    setError(null);
    setModelUnavailable(false);
  };

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Disease detection"
        title="Classify a leaf photo"
        description="Upload a clear photo of a single affected leaf. The convolutional network returns the most likely class, its confidence and practical guidance for the problem."
      />

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Scan className="h-4 w-4 text-brand-600" aria-hidden="true" />
                Upload an image
              </CardTitle>
              <CardDescription>
                JPEG, PNG or WebP up to 10 MB. A flat, well-lit photo of one leaf gives
                the best result.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <ImageDropzone file={file} onFile={setFile} disabled={isPredicting} />

              {error ? (
                <Alert tone="danger" title="The analysis failed">
                  {error}
                </Alert>
              ) : null}

              <div className="flex flex-col gap-2 sm:flex-row">
                <Button
                  onClick={() => void runPrediction()}
                  disabled={!file}
                  isLoading={isPredicting}
                  fullWidth
                >
                  {isPredicting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                      Analysing…
                    </>
                  ) : (
                    <>
                      <Leaf className="h-4 w-4" aria-hidden="true" />
                      Analyse the leaf
                    </>
                  )}
                </Button>
                {file || result ? (
                  <Button variant="outline" onClick={reset} disabled={isPredicting}>
                    Start over
                  </Button>
                ) : null}
              </div>

              <div className="rounded-xl border border-border bg-muted/40 p-4">
                <p className="flex items-center gap-2 text-sm font-semibold">
                  <AlertTriangle className="h-4 w-4 text-amber-600" aria-hidden="true" />
                  Getting the best result
                </p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                  <li>Photograph one leaf against a plain background.</li>
                  <li>Fill the frame and keep the leaf in focus.</li>
                  <li>Use daylight rather than a torch or flash.</li>
                  <li>Include the damaged area - the model classifies symptoms.</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-3">
          {modelUnavailable ? (
            <ModelUnavailableState
              modelName="The crop disease classifier"
              trainCommand={MODEL_UNAVAILABLE_HINT}
            />
          ) : result ? (
            <DiseaseResultCard result={result} />
          ) : (
            <div className="flex h-full min-h-[320px] flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-card/40 px-6 py-16 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500/12 text-brand-600 dark:text-brand-400">
                <Leaf className="h-7 w-7" aria-hidden="true" />
              </div>
              <div className="space-y-1">
                <p className="font-display text-base font-semibold">No analysis yet</p>
                <p className="mx-auto max-w-sm text-sm text-muted-foreground">
                  Upload a leaf photo on the left and the diagnosis, the confidence and
                  the treatment guidance will appear here.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
