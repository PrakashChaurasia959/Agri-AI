import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Droplets, FlaskConical, Sprout, Thermometer, Waves } from 'lucide-react';

import { PageContainer, PageHeader } from '@/components/layout/AppLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input, Select } from '@/components/ui/Form';
import { Alert } from '@/components/ui/Alert';
import { CropResultCard } from '@/components/features/CropResultCard';
import { ModelUnavailableState } from '@/components/ui/States';
import { useToast } from '@/contexts/ToastContext';
import { cropService } from '@/services/crops';
import { ApiError } from '@/services/api';
import { SOIL_TYPES } from '@/utils/constants';
import type { CropRecommendation } from '@/types';

const schema = z.object({
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
  soil_type: z.string().max(40).optional(),
  location: z.string().max(160).optional(),
});

type CropForm = z.infer<typeof schema>;

export function CropRecommendationPage() {
  const toast = useToast();
  const [result, setResult] = useState<CropRecommendation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modelUnavailable, setModelUnavailable] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CropForm>({
    resolver: zodResolver(schema),
    defaultValues: {
      nitrogen: 80,
      phosphorus: 40,
      potassium: 40,
      temperature: 25,
      humidity: 60,
      rainfall: 100,
      ph: 6.5,
      soil_type: 'loamy',
      location: '',
    },
  });

  const onSubmit = handleSubmit(async (values) => {
    setError(null);
    setModelUnavailable(false);
    try {
      const recommendation = await cropService.recommend({
        nitrogen: values.nitrogen,
        phosphorus: values.phosphorus,
        potassium: values.potassium,
        temperature: values.temperature,
        humidity: values.humidity,
        rainfall: values.rainfall,
        ph: values.ph,
        soil_type: values.soil_type?.trim() ? values.soil_type.trim() : null,
        location: values.location?.trim() ? values.location.trim() : null,
      });
      setResult(recommendation);
      toast.success(
        'Recommendation ready.',
        recommendation.top_crop
          ? `${recommendation.top_crop} is the best match.`
          : undefined,
      );
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 503) {
        setModelUnavailable(true);
        setResult(null);
      } else if (caught instanceof ApiError && caught.status === 401) {
        setError('Please sign in to get crop recommendations.');
        toast.error('Authentication required', 'Please sign in to continue.');
      } else {
        const message =
          caught instanceof Error ? caught.message : 'The recommendation failed.';
        setError(message);
        toast.error('Recommendation failed', message);
      }
    }
  });

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Crop recommendation"
        title="Find the crop that fits your field"
        description="Enter your soil nutrients and the season's climate. A gradient-boosted tree trained on 2,200 labelled samples ranks the 22 crops that suit those conditions."
      />

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FlaskConical className="h-4 w-4 text-earth-600" aria-hidden="true" />
                Soil and climate readings
              </CardTitle>
              <CardDescription>
                Every field is required. The values below are the medians of the
                training data and make a sensible starting point.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={onSubmit} className="space-y-5" noValidate>
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

                <Select
                  label="Soil type (optional)"
                  error={errors.soil_type?.message}
                  {...register('soil_type')}
                >
                  <option value="">Not specified</option>
                  {SOIL_TYPES.map((soil) => (
                    <option key={soil} value={soil}>
                      {soil[0].toUpperCase() + soil.slice(1)}
                    </option>
                  ))}
                </Select>

                <Input
                  label="Location (optional)"
                  placeholder="Nashik, Maharashtra"
                  hint="Stored with the recommendation for your records."
                  error={errors.location?.message}
                  {...register('location')}
                />

                {error ? (
                  <Alert tone="danger" title="The recommendation failed">
                    {error}
                  </Alert>
                ) : null}

                <Button type="submit" fullWidth isLoading={isSubmitting}>
                  <Sprout className="h-4 w-4" aria-hidden="true" />
                  Recommend crops
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-3">
          {modelUnavailable ? (
            <ModelUnavailableState
              modelName="The crop recommendation model"
              trainCommand="cd backend && python -m ml.train_crop_model"
            />
          ) : result ? (
            <CropResultCard result={result} />
          ) : (
            <div className="flex h-full min-h-[320px] flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-border bg-card/40 px-6 py-16 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500/12 text-brand-600 dark:text-brand-400">
                <Sprout className="h-7 w-7" aria-hidden="true" />
              </div>
              <div className="space-y-1">
                <p className="font-display text-base font-semibold">No recommendation yet</p>
                <p className="mx-auto max-w-sm text-sm text-muted-foreground">
                  Fill in the readings on the left. The model returns a ranked list of
                  crops with a match score for each one.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
