import { Link } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  BarChart3,
  CloudSun,
  Leaf,
  ShieldCheck,
  Sprout,
  TrendingUp,
} from 'lucide-react';

import { Brand } from '@/components/layout/Brand';
import { Card, CardContent } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Spinner';
import { useAsync } from '@/hooks/useAsync';
import { systemService } from '@/services';
import { formatMetric, formatPercent } from '@/utils/format';
import { PRIMARY_NAV } from '@/utils/constants';

export function LandingPage() {
  const models = useAsync(() => systemService.models(), []);

  const features = [
    {
      icon: Leaf,
      title: 'Disease detection',
      body: 'Upload a leaf photo and a MobileNetV2 classifier trained on 54,381 PlantVillage images returns the disease, the confidence and practical prevention and treatment guidance.',
    },
    {
      icon: Sprout,
      title: 'Crop recommendation',
      body: 'Enter your soil nutrients, temperature, humidity, rainfall and pH. A model trained on 2,200 labelled samples ranks the 22 most suitable crops with an explanation.',
    },
    {
      icon: TrendingUp,
      title: 'Yield estimation',
      body: 'Estimate the expected harvest in tonnes per hectare from the same agronomic inputs, with a confidence interval so you can plan for a range rather than a single number.',
    },
    {
      icon: CloudSun,
      title: 'Field weather',
      body: 'Live current conditions and a seven day forecast for your exact field, geocoded through Open-Meteo. The API key never leaves the server.',
    },
  ];

  const measured = models.data?.models.filter((model) => model.available) ?? [];

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Brand />
          <div className="flex items-center gap-2">
            <Link
              to="/login"
              className="focus-ring inline-flex h-10 items-center justify-center rounded-lg px-4 text-sm font-medium transition hover:bg-muted"
            >
              Sign in
            </Link>
            <Link
              to="/register"
              className="focus-ring inline-flex h-10 items-center justify-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700"
            >
              Get started
            </Link>
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-grid-light bg-grid-dark opacity-50 dark:opacity-30" />
        <div className="relative mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-28 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <span className="inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 text-xs font-medium text-brand-700 dark:text-brand-300">
              <Activity className="h-3.5 w-3.5" aria-hidden="true" />
              Deep learning for smallholder agriculture
            </span>
            <h1 className="mt-6 font-display text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
              Diagnose disease, choose the right crop and{' '}
              <span className="gradient-text">forecast your harvest</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-base text-muted-foreground sm:text-lg">
              AgriVision AI turns a leaf photograph, a soil reading and a weather
              forecast into decisions you can act on. Every model was trained on real
              datasets and every number the platform shows is a measured metric - never
              an estimate presented as a fact.
            </p>
            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link
                to="/register"
                className="focus-ring inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-brand-600 px-7 text-base font-medium text-white shadow-sm transition hover:bg-brand-700"
              >
                Create a free account
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link
                to="/login"
                className="focus-ring inline-flex h-12 items-center justify-center rounded-xl border border-border bg-card px-7 text-base font-medium transition hover:bg-muted"
              >
                Sign in
              </Link>
            </div>
          </div>

          <div className="mx-auto mt-16 grid max-w-5xl gap-4 sm:grid-cols-3">
            <div className="rounded-2xl border border-border bg-card/70 p-6 text-center backdrop-blur">
              <p className="font-display text-3xl font-bold">38</p>
              <p className="mt-1 text-sm text-muted-foreground">disease classes</p>
            </div>
            <div className="rounded-2xl border border-border bg-card/70 p-6 text-center backdrop-blur">
              <p className="font-display text-3xl font-bold">22</p>
              <p className="mt-1 text-sm text-muted-foreground">crops ranked per query</p>
            </div>
            <div className="rounded-2xl border border-border bg-card/70 p-6 text-center backdrop-blur">
              <p className="font-display text-3xl font-bold">100%</p>
              <p className="mt-1 text-sm text-muted-foreground">of displayed metrics are measured</p>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-border bg-card/30 py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-display text-3xl font-bold tracking-tight">
              Everything a farmer needs, in one place
            </h2>
            <p className="mt-3 text-muted-foreground">
              Four machine-learning tools, one weather integration and a dashboard that
              keeps a complete record of every decision you made.
            </p>
          </div>

          <div className="mt-12 grid gap-6 md:grid-cols-2">
            {features.map((feature) => (
              <Card key={feature.title} className="h-full transition hover:shadow-glow">
                <CardContent className="space-y-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-500/12 text-brand-600 dark:text-brand-400">
                    <feature.icon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <h3 className="font-display text-lg font-semibold">{feature.title}</h3>
                  <p className="text-sm leading-relaxed text-muted-foreground">{feature.body}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-border py-20">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-display text-3xl font-bold tracking-tight">
              Model status on this server
            </h2>
            <p className="mt-3 text-muted-foreground">
              Read live from the API. A model that is not installed is reported as
              unavailable - AgriVision never shows a fabricated result.
            </p>
          </div>

          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {models.isLoading
              ? Array.from({ length: 3 }).map((_, index) => (
                  <Card key={index}>
                    <CardContent className="space-y-3">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-8 w-32" />
                      <Skeleton className="h-3 w-full" />
                    </CardContent>
                  </Card>
                ))
              : measured.map((model) => (
                  <Card key={model.key}>
                    <CardContent className="space-y-3">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium">{model.display_name}</p>
                        <span className="flex h-2 w-2 rounded-full bg-brand-500" />
                      </div>
                      <p className="font-display text-2xl font-bold">
                        {model.metrics?.accuracy !== undefined
                          ? formatPercent(model.metrics.accuracy)
                          : model.model_version
                            ? `v${model.model_version}`
                            : 'Available'}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {model.metrics?.accuracy !== undefined
                          ? `Test accuracy · ${
                              model.metrics.f1_macro !== undefined
                                ? `F1 ${formatMetric(model.metrics.f1_macro, 4)}`
                                : `MAE ${formatMetric(model.metrics.mae, 4)}`
                            }`
                          : model.message}
                      </p>
                    </CardContent>
                  </Card>
                ))}
          </div>

          {models.data && measured.length < models.data.total_count ? (
            <p className="mt-6 text-center text-sm text-muted-foreground">
              {models.data.total_count - measured.length} of {models.data.total_count}{' '}
              models are not installed on this server. The API answers with a clear
              &ldquo;not available&rdquo; response for those features.
            </p>
          ) : null}
        </div>
      </section>

      <section className="border-t border-border bg-brand-950 py-20 text-white">
        <div className="mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          <ShieldCheck className="mx-auto h-10 w-10 text-brand-400" aria-hidden="true" />
          <h2 className="mt-6 font-display text-3xl font-bold tracking-tight">
            Honest by design
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-white/75">
            AgriVision AI was built for a final-year engineering project where the
            results have to be reproducible. Every endpoint returns real data or a clear
            explanation of why it cannot - there are no placeholder buttons, no mock
            weather and no invented confidences.
          </p>
          <div className="mt-10 grid gap-4 text-left sm:grid-cols-3">
            {[
              {
                icon: BarChart3,
                title: 'Measured metrics',
                body: 'Accuracy, MAE and R² come from a held-out test split and are stored next to the model.',
              },
              {
                icon: ShieldCheck,
                title: 'No invented data',
                body: 'A missing model or an unreachable database produces an explicit error, never a placeholder answer.',
              },
              {
                icon: Activity,
                title: 'Full audit trail',
                body: 'Every prediction, profile change and administrative action is recorded and reviewable.',
              },
            ].map((item) => (
              <div key={item.title} className="rounded-2xl border border-white/10 bg-white/5 p-5">
                <item.icon className="h-5 w-5 text-brand-400" aria-hidden="true" />
                <h3 className="mt-3 font-display text-base font-semibold">{item.title}</h3>
                <p className="mt-1.5 text-sm text-white/65">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-border py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <h2 className="text-center font-display text-3xl font-bold tracking-tight">
            Explore the platform
          </h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {PRIMARY_NAV.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="focus-ring group flex items-start gap-4 rounded-2xl border border-border bg-card p-5 transition hover:border-brand-400/60 hover:shadow-glow"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-muted text-brand-600 transition group-hover:bg-brand-500/12 dark:text-brand-400">
                  <item.icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <div>
                  <p className="font-display text-base font-semibold">{item.label}</p>
                  <p className="mt-0.5 text-sm text-muted-foreground">{item.description}</p>
                </div>
              </Link>
            ))}
            <div className="flex items-center justify-center rounded-2xl border border-dashed border-border p-5">
              <Link
                to="/register"
                className="focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-medium transition hover:bg-muted"
              >
                Start for free
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-border bg-card/40">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 py-8 text-center sm:px-6 md:flex-row md:text-left lg:px-8">
          <Brand />
          <p className="text-xs text-muted-foreground">
            A final-year engineering project. Weather data by Open-Meteo.
          </p>
        </div>
      </footer>
    </div>
  );
}
