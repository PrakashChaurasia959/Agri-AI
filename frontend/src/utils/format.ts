/** Formatting helpers shared by the whole UI. */

const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
});

const dateFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' });

const numberFormatter = new Intl.NumberFormat(undefined, {
  maximumFractionDigits: 2,
});

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return dateTimeFormatter.format(parsed);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return dateFormatter.format(parsed);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function formatNumber(value: unknown): string {
  if (!isFiniteNumber(value)) return '—';
  return numberFormatter.format(value);
}

export function formatPercent(value: unknown, fractionDigits = 1): string {
  if (!isFiniteNumber(value)) return '—';
  return `${(value * 100).toFixed(fractionDigits)}%`;
}

export function formatMetric(value: unknown, fractionDigits = 3): string {
  if (!isFiniteNumber(value)) return '—';
  return value.toFixed(fractionDigits);
}

/**
 * Return only the scalar entries of a model-metrics object.
 *
 * Metadata such as ``per_class`` is a nested object, not a number, so feeding
 * it to ``toFixed`` used to crash the result cards. Rendering only numeric
 * metrics keeps the summary honest and the UI stable.
 */
export function scalarMetrics(
  metrics: Record<string, unknown> | null | undefined,
): Array<[string, number]> {
  if (!metrics) return [];
  return Object.entries(metrics).filter((entry): entry is [string, number] =>
    isFiniteNumber(entry[1]),
  );
}

/** Turn `Tomato___Late_blight` into `Tomato - Late blight`. */
export function humaniseClassName(value: string | null | undefined): string {
  if (!value) return 'Unknown';
  const parts = value
    .split('___')
    .map((part) => part.replace(/_/g, ' ').trim())
    .filter(Boolean);
  if (parts.length === 0) return 'Unknown';
  if (parts.length === 1) return titleCase(parts[0]);
  return `${titleCase(parts[0])} - ${titleCase(parts.slice(1).join(' '))}`;
}

export function titleCase(value: string): string {
  return value
    .split(' ')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function relativeTime(value: string | null | undefined): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  const diffSeconds = Math.round((parsed.getTime() - Date.now()) / 1000);
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ['year', 31_536_000],
    ['month', 2_592_000],
    ['week', 604_800],
    ['day', 86_400],
    ['hour', 3_600],
    ['minute', 60],
  ];
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  for (const [unit, seconds] of units) {
    if (Math.abs(diffSeconds) >= seconds) {
      return formatter.format(Math.round(diffSeconds / seconds), unit);
    }
  }
  return formatter.format(diffSeconds, 'second');
}

export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
}
