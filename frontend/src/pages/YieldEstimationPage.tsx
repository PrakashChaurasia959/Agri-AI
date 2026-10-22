import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Droplets, FlaskConical, Scale, Thermometer, TrendingUp, Waves } from 'lucide-react';

import { PageContainer, PageHeader } from '@/components/layout/AppLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input, Select } from '@/components/ui/Form';
import { Alert } from '@/components/ui/Alert';
import { YieldResultCard } from '@/components/features/YieldResultCard';
import { ModelUnavailableState } from '@/components/ui/States';
import { useToast } from '@/contexts/ToastContext';
import { yieldService } from '@/services/crops';
import { ApiError } from '@/services/api';
import { SUPPORTED_CROPS } from '@/utils/constants';
import type { YieldPrediction } from '@/types';

const schema = z.object({
  crop_type: z
    .string()
    .min(2, 'Choose a crop.')
    .max(60, 'That crop name is too long.'),
  area_ha: z.coerce
    .number({ invalid_type_error: 'Enter a number.' })
    .gt(0, 'The area must be greater than zero.')
    .max(100000, 'That area is too large.'),
  nitrogen: z.coerce
    .number({ invalid_type_error: 'Enter a number.' })
    .min(0, 'Cannot be negative.')
    .max(300, 'The maximum is 300 mg/kg.'),
  phosphorus: z.coerce
    .number({ invalid_type_error: 'Enter a number.' })
    .min(0, 'Cannot be negative.')
    .max(300, 'The maximum is 300 mg/kg.'),
  potassium: z.coerce
    .number({ invalid_type_error: 'Enter a number.' })
    .min(0, 'Cannot be negative.')
    .max(300, 'The maximum is 300 mg/kg.'),
  temperature: z.coerce
    .number({ invalid_type_error: 'Enter a number.' })
    .min(0, 'Cannot be negative.')
    .max(60, 'The maximum is 60 °C.'),
  humidity: z.coerce
    .number({ invalid_type_error: 'Enter a number.' })
    .min(0, 'Cannot be negative.')
    .max(100, 'Humidity is a percentage.'),
  rainfall: z.coerce
    .number({ invalid_type_error: 'Enter a number.' })
    .min(0, 'Cannot be negative.')
    .max(500, 'The maximum is 500 mm.'),
  ph: z.coerce
    .number({ invalid_type_error: 'Enter a number.' })
    .min(0, 'The minimum is 0.')
    .max(14, 'The maximum is 14.'),
});

type YieldForm = z.infer<typeof schema>;

export function YieldEstimationPage() {
  const toast = useToast();
  const [result, setResult] = useState<YieldPrediction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modelUnavailable, setModelUnavailable] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<YieldForm>({
    resolver: zodResolver(schema),
    defaultValues: {
      crop_type: 'rice',
      area_ha: 1,
      nitrogen: 80,
      phosphorus: 40,
      potassium: 40,
      temperature: 25,
      humidity: 60,
      rainfall: 100,
      ph: 6.5,
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    setModelUnavailable(false);
    try {
      const prediction = await yieldService.predict(values);
      setResult(prediction);
      toast.success(
        'Yield estimate ready.',
        prediction.estimated_yield === null
          ? undefined
          : `${prediction.estimated_yield.toFixed(2)} ${prediction.yield_unit} expected.`,
      );
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 503) {
        setModelUnavailable(true);
        setResult(null);
      } else {
        const message =
          caught instanceof Error ? caught.message : 'The estimate could not be produced.';
        setError(message);
        toast.error('Yield estimation failed', message);
      }
    }
  });

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Yield estimation"
        title="Estimate the harvest for your field"
        description="A gradient-boosted regressor trained on 25,000 labelled crop records predicts the yield in tonnes per hectare, together with a range you can plan around."
      />

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Scale className="h-4 w-4 text-sky-600" aria-hidden="true" />
                Field details
              </CardTitle>
              <CardDescription>
                The same agronomic readings used for crop recommendation, plus the crop
                you are growing and the area you have planted.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={onSubmit} className="space-y-5" noValidate>
                <Select
                  label="Crop"
                  error={errors.crop_type?.message}
                  {...register('crop_type')}
                >
                  {SUPPORTED_CROPS.map((crop) => (
                    <option key={crop} value={crop}>
                      {crop[0].toUpperCase() + crop.slice(1)}
                    </option>
                  ))}
                </Select>

                <Input
                  label="Area"
                  type="number"
                  step="any"
                  icon={<Scale className="h-4 w-4" aria-hidden="true" />}
                  hint="hectares"
                  error={errors.area_ha?.message}
                  {...register('area_ha')}
                />

                <div className="grid gap-4 sm:grid-cols-3">
                  <Input
                    label="Nitrogen"
                    type="number"
                    step="any"
                    icon={<FlaskConical className="h-4 w-4" aria-hidden="true" />}
                    hint="mg/kg"
                    error={errors.nitrogen?.message}
                    {...register('nitrogen')}
                  />
                  <Input
                    label="Phosphorus"
                    type="number"
                    step="any"
                    icon={<FlaskConical className="h-4 w-4" aria-hidden="true" />}
                    hint="mg/kg"
                    error={errors.phosphorus?.message}
                    {...register('phosphorus')}
                  />
                  <Input
                    label="Potassium"
                    type="number"
                    step="any"
                    icon={<FlaskConical className="h-4 w-4" aria-hidden="true" />}
                    hint="mg/kg"
                    error={errors.potassium?.message}
                    {...register('potassium')}
                  />
                </div>

                <div className="grid gap-4 sm:grid-cols-3">
                  <Input
                    label="Temperature"
                    type="number"
                    step="any"
                    icon={<Thermometer className="h-4 w-4" aria-hidden="true" />}
                    hint="°C"
                    error={errors.temperature?.message}
                    {...register('temperature')}
                  />
                  <Input
                    label="Humidity"
                    type="number"
                    step="any"
                    icon={<Droplets className="h-4 w-4" aria-hidden="true" />}
                    hint="%"
                    error={errors.humidity?.message}
                    {...register('humidity')}
                  />
                  <Input
                    label="Rainfall"
                    type="number"
                    step="any"
                    icon={<Waves className="h-4 w-4" aria-hidden="true" />}
                    hint="mm"
                    error={errors.rainfall?.message}
                    {...register('rainfall')}
                  />
                </div>

                <Input
                  label="Soil pH"
                  type="number"
                  step="0.1"
                  hint="between 0 and 14"
                  error={errors.ph?.message}
                  {...register('ph')}
                />

                {error ? (
                  <Alert tone="danger" title="The estimate failed">
                    {error}
                  </Alert>
                ) : null}

                <Button type="submit" fullWidth isLoading={isSubmitting}>
                  <TrendingUp className="h-4 w-4" aria-hidden="true" />
                  Estimate the yield
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-3">
          {modelUnavailable ? (
            <ModelUnavailableState
              modelName="The crop yield model"
              trainCommand="cd backend && python -m ml.train_yield_model"
            />
          ) : result ? (
            <YieldResultCard result={result} />
          ) : (
            <div className="flex h-full min-h-[320px] flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-card/40 px-6 py-16 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-sky-500/12 text-sky-600 dark:text-sky-400">
                <TrendingUp className="h-7 w-7" aria-hidden="true" />
              </div>
              <div className="space-y-1">
                <p className="font-display text-base font-semibold">No estimate yet</p>
                <p className="mx-auto max-w-sm text-sm text-muted-foreground">
                  Fill in the field details on the left and the expected harvest, the
                  per-hectare figure and the planning range appear here.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
