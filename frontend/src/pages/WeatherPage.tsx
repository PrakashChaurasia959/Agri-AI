import { useEffect, useState, type ReactNode } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  CloudRain,
  CloudSun,
  Droplets,
  Gauge,
  MapPin,
  Search,
  Thermometer,
  Wind,
} from 'lucide-react';

import { PageContainer, PageHeader } from '@/components/layout/AppLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Form';
import { Badge } from '@/components/ui/Badge';
import { Alert } from '@/components/ui/Alert';
import { SkeletonRows } from '@/components/ui/Spinner';
import { EmptyState, ErrorState } from '@/components/ui/States';
import { ForecastChart } from '@/components/charts/Charts';
import { useAsync } from '@/hooks/useAsync';
import { useDebounced } from '@/hooks/useDebounced';
import { weatherService } from '@/services';
import { formatDateTime, formatNumber } from '@/utils/format';
import { WEATHER_CODES } from '@/utils/constants';
import type { WeatherLocation } from '@/types';

const searchSchema = z.object({
  query: z
    .string()
    .min(2, 'Type at least two characters.')
    .max(120, 'That search term is too long.'),
});

type SearchForm = z.infer<typeof searchSchema>;

/** Nashik, India - used only as a starting point for the first lookup. */
const DEFAULT_LOCATION = { latitude: 19.9975, longitude: 73.7898, name: 'Nashik, India' };

export function WeatherPage() {
  const [selected, setSelected] = useState<WeatherLocation | null>(null);
  const [search, setSearch] = useState('');
  const [searchError, setSearchError] = useState<string | null>(null);

  const debouncedSearch = useDebounced(search, 400);

  const results = useAsync(
    () => weatherService.search(debouncedSearch),
    [debouncedSearch],
    { enabled: debouncedSearch.trim().length >= 2 },
  );

  const current = useAsync(
    () =>
      weatherService.current(
        selected?.latitude ?? DEFAULT_LOCATION.latitude,
        selected?.longitude ?? DEFAULT_LOCATION.longitude,
        selected?.name ?? DEFAULT_LOCATION.name,
      ),
    [selected],
  );

  const forecast = useAsync(
    () =>
      weatherService.forecast(
        selected?.latitude ?? DEFAULT_LOCATION.latitude,
        selected?.longitude ?? DEFAULT_LOCATION.longitude,
        7,
        selected?.name ?? DEFAULT_LOCATION.name,
      ),
    [selected],
  );

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SearchForm>({
    resolver: zodResolver(searchSchema),
    defaultValues: { query: '' },
  });

  useEffect(() => {
    setSearchError(null);
  }, [debouncedSearch]);

  const onSubmit = handleSubmit((values) => {
    const trimmed = values.query.trim();
    if (trimmed.length < 2) {
      setSearchError('Type at least two characters.');
      return;
    }
    setSearch(trimmed);
  });

  const weather = current.data?.current;
  const location = current.data?.location ?? selected;

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Weather"
        title="Field weather"
        description="Live conditions and a seven day forecast for your exact field, served by Open-Meteo. The lookup happens on the server, so no API key is exposed to the browser."
      />

      <Card className="mb-6">
        <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <form onSubmit={onSubmit} className="flex-1 space-y-2">
            <Input
              label="Search for a place"
              placeholder="Nashik, Pune, Nagpur…"
              icon={<Search className="h-4 w-4" aria-hidden="true" />}
              error={errors.query?.message ?? searchError}
              {...register('query', { onChange: (event) => setSearch(event.target.value) })}
            />
          </form>
          <Button type="submit" className="sm:mb-0">
            <MapPin className="h-4 w-4" aria-hidden="true" />
            Find location
          </Button>
        </CardContent>
      </Card>

      {results.data && results.data.length > 0 ? (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle className="text-base">Matching places</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {results.data.map((place) => (
              <button
                key={`${place.name}-${place.latitude}-${place.longitude}`}
                type="button"
                onClick={() => setSelected(place)}
                className="focus-ring inline-flex items-center gap-2 rounded-full border border-border px-3 py-1.5 text-sm transition hover:border-brand-400/60 hover:bg-muted"
              >
                <MapPin className="h-3.5 w-3.5 text-brand-600" aria-hidden="true" />
                {place.name}
                {place.admin1 ? <span className="text-muted-foreground">{place.admin1}</span> : null}
              </button>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {results.error ? (
        <Alert tone="warning" className="mb-6" title="The location search failed">
          {results.error}
        </Alert>
      ) : null}

      {current.error ? (
        <ErrorState
          title="The weather service is unavailable"
          description={current.error}
          onRetry={current.reload}
        />
      ) : null}

      {current.isLoading ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <Card>
              <CardContent className="pt-6">
                <SkeletonRows rows={4} />
              </CardContent>
            </Card>
          </div>
          <Card>
            <CardContent className="pt-6">
              <SkeletonRows rows={4} />
            </CardContent>
          </Card>
        </div>
      ) : current.data ? (
        <>
          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader className="flex-row items-start justify-between gap-4 space-y-0">
                <div>
                  <CardTitle className="text-2xl">
                    {weather?.temperature === null || weather?.temperature === undefined
                      ? '—'
                      : `${weather.temperature.toFixed(1)}°C`}
                  </CardTitle>
                  <CardDescription className="mt-1">
                    {location?.name}
                    {location?.admin1 ? `, ${location.admin1}` : ''}
                    {location?.country ? ` · ${location.country}` : ''}
                  </CardDescription>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <CloudSun className="h-10 w-10 text-brand-600" aria-hidden="true" />
                  <Badge tone="brand">
                    {weather?.weather_description ??
                      (weather?.weather_code !== null && weather?.weather_code !== undefined
                        ? WEATHER_CODES[weather.weather_code]?.label ?? 'Unknown'
                        : 'Unknown')}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <Metric
                    icon={<Thermometer className="h-4 w-4" />}
                    label="Feels like"
                    value={
                      weather?.apparent_temperature === null ||
                      weather?.apparent_temperature === undefined
                        ? '—'
                        : `${weather.apparent_temperature.toFixed(1)}°C`
                    }
                  />
                  <Metric
                    icon={<Droplets className="h-4 w-4" />}
                    label="Humidity"
                    value={
                      weather?.humidity === null || weather?.humidity === undefined
                        ? '—'
                        : `${weather.humidity.toFixed(0)}%`
                    }
                  />
                  <Metric
                    icon={<CloudRain className="h-4 w-4" />}
                    label="Precipitation"
                    value={
                      weather?.precipitation === null ||
                      weather?.precipitation === undefined
                        ? '—'
                        : `${weather.precipitation.toFixed(1)} mm`
                    }
                  />
                  <Metric
                    icon={<Wind className="h-4 w-4" />}
                    label="Wind"
                    value={
                      weather?.wind_speed === null || weather?.wind_speed === undefined
                        ? '—'
                        : `${weather.wind_speed.toFixed(1)} km/h`
                    }
                  />
                  <Metric
                    icon={<Gauge className="h-4 w-4" />}
                    label="Pressure"
                    value={
                      weather?.surface_pressure === null ||
                      weather?.surface_pressure === undefined
                        ? '—'
                        : `${weather.surface_pressure.toFixed(0)} hPa`
                    }
                  />
                  <Metric
                    icon={<CloudSun className="h-4 w-4" />}
                    label="Cloud cover"
                    value={
                      weather?.cloud_cover === null || weather?.cloud_cover === undefined
                        ? '—'
                        : `${weather.cloud_cover.toFixed(0)}%`
                    }
                  />
                  <Metric
                    icon={<Droplets className="h-4 w-4" />}
                    label="Rainfall"
                    value={
                      weather?.rainfall === null || weather?.rainfall === undefined
                        ? '—'
                        : `${weather.rainfall.toFixed(1)} mm`
                    }
                  />
                  <Metric
                    icon={<Wind className="h-4 w-4" />}
                    label="Wind direction"
                    value={
                      weather?.wind_direction === null ||
                      weather?.wind_direction === undefined
                        ? '—'
                        : `${weather.wind_direction}°`
                    }
                  />
                </dl>
                <p className="mt-4 text-xs text-muted-foreground">
                  Source: {current.data.source} · fetched{' '}
                  {formatDateTime(current.data.fetched_at)}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">7 day forecast</CardTitle>
                <CardDescription>Daily temperature range.</CardDescription>
              </CardHeader>
              <CardContent>
                {forecast.isLoading ? (
                  <SkeletonRows rows={5} />
                ) : forecast.error ? (
                  <p className="py-6 text-center text-sm text-muted-foreground">
                    {forecast.error}
                  </p>
                ) : (forecast.data?.daily ?? []).length === 0 ? (
                  <p className="py-6 text-center text-sm text-muted-foreground">
                    No forecast rows were returned.
                  </p>
                ) : (
                  <ForecastChart
                    data={(forecast.data?.daily ?? []).map((day) => ({
                      date: day.date.slice(5),
                      temperature_max: day.temperature_max ?? 0,
                      temperature_min: day.temperature_min ?? 0,
                      precipitation: day.precipitation_sum ?? 0,
                    }))}
                    height={220}
                  />
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="text-base">Day by day</CardTitle>
              <CardDescription>
                Rain probability and wind, straight from the forecast provider.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {forecast.data && forecast.data.daily.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[640px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="py-2 pr-4 font-medium">Date</th>
                        <th className="py-2 pr-4 font-medium">Conditions</th>
                        <th className="py-2 pr-4 font-medium">Min / max</th>
                        <th className="py-2 pr-4 font-medium">Rain</th>
                        <th className="py-2 font-medium">Wind</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {forecast.data.daily.map((day) => (
                        <tr key={day.date}>
                          <td className="py-2.5 pr-4 font-medium">{day.date}</td>
                          <td className="py-2.5 pr-4 text-muted-foreground">
                            {day.weather_description ??
                              (day.weather_code !== null && day.weather_code !== undefined
                                ? WEATHER_CODES[day.weather_code]?.label ?? 'Unknown'
                                : 'Unknown')}
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            {day.temperature_min === null ? '—' : day.temperature_min.toFixed(0)}° /{' '}
                            {day.temperature_max === null ? '—' : day.temperature_max.toFixed(0)}°
                          </td>
                          <td className="py-2.5 pr-4 tabular-nums">
                            {day.precipitation_probability_max === null
                              ? '—'
                              : `${day.precipitation_probability_max.toFixed(0)}%`}
                            {day.precipitation_sum !== null ? (
                              <span className="text-muted-foreground">
                                {' '}
                                ({formatNumber(day.precipitation_sum)} mm)
                              </span>
                            ) : null}
                          </td>
                          <td className="py-2.5 tabular-nums">
                            {day.wind_speed_max === null
                              ? '—'
                              : `${day.wind_speed_max.toFixed(0)} km/h`}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState title="No forecast available" description="The provider returned no daily rows for this location." />
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </PageContainer>
  );
}

function Metric({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-muted/40 p-3">
      <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span className="text-brand-600 dark:text-brand-400">{icon}</span>
        {label}
      </dt>
      <dd className="mt-1 font-display text-lg font-semibold">{value}</dd>
    </div>
  );
}
