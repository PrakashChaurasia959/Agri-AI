import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { cn } from '@/utils/cn';

const AXIS_STYLE = { fontSize: 11, fill: 'currentColor' } as const;

export interface ConfidencePointData {
  date: string;
  average_confidence: number;
  predictions: number;
}

/** Number of predictions per day across the selected window. */
export function DailyActivityChart({
  data,
  height = 260,
}: {
  data: Array<{ date: string; value: number }>;
  height?: number;
}) {
  if (!data.length) {
    return (
      <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">
        No predictions in this period yet.
      </div>
    );
  }

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -24, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
          <XAxis
            dataKey="date"
            tick={AXIS_STYLE}
            tickLine={false}
            axisLine={false}
            minTickGap={18}
          />
          <YAxis tick={AXIS_STYLE} tickLine={false} axisLine={false} allowDecimals={false} />
          <Tooltip
            cursor={{ fill: 'hsl(var(--muted))' }}
            contentStyle={{
              borderRadius: 12,
              border: '1px solid hsl(var(--border))',
              fontSize: 12,
            }}
            formatter={(value: number) => [value, 'Predictions']}
          />
          <Bar dataKey="value" name="Predictions" fill="#4ba148" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Average model confidence over time. */
export function ConfidenceTrendChart({
  data,
  height = 260,
}: {
  data: ConfidencePointData[];
  height?: number;
}) {
  if (!data.length) {
    return (
      <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">
        No predictions in this period yet.
      </div>
    );
  }

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="confidenceFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4ba148" stopOpacity={0.45} />
              <stop offset="100%" stopColor="#4ba148" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
          <XAxis
            dataKey="date"
            tick={AXIS_STYLE}
            tickLine={false}
            axisLine={false}
            minTickGap={24}
          />
          <YAxis
            domain={[0, 1]}
            tick={AXIS_STYLE}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: number) => `${Math.round(value * 100)}%`}
          />
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              border: '1px solid hsl(var(--border))',
              background: 'hsl(var(--popover, var(--card)))',
              fontSize: 12,
            }}
            formatter={(value: number) => [`${(value * 100).toFixed(1)}%`, 'Avg confidence']}
          />
          <Area
            type="monotone"
            dataKey="average_confidence"
            stroke="#4ba148"
            strokeWidth={2}
            fill="url(#confidenceFill)"
            dot={false}
            activeDot={{ r: 4 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export interface CropDistributionData {
  crop: string;
  count: number;
  average_confidence: number;
}

/** How often each crop has been recommended. */
export function CropDistributionChart({
  data,
  height = 280,
}: {
  data: CropDistributionData[];
  height?: number;
}) {
  if (!data.length) {
    return (
      <div className="flex h-[280px] items-center justify-center text-sm text-muted-foreground">
        No crop recommendations yet.
      </div>
    );
  }

  const palette = [
    '#4ba148',
    '#bc8150',
    '#2f9e95',
    '#7c6bd6',
    '#d98b3a',
    '#3b82f6',
    '#c2569a',
    '#6b8f2f',
  ];

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
          <XAxis type="number" tick={AXIS_STYLE} tickLine={false} axisLine={false} allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="crop"
            tick={AXIS_STYLE}
            tickLine={false}
            axisLine={false}
            width={110}
          />
          <Tooltip
            cursor={{ fill: 'hsl(var(--muted))' }}
            contentStyle={{
              borderRadius: 12,
              border: '1px solid hsl(var(--border))',
              fontSize: 12,
            }}
          />
          <Bar dataKey="count" name="Recommendations" radius={[0, 6, 6, 0]} barSize={18}>
            {data.map((entry, index) => (
              <Cell key={entry.crop} fill={palette[index % palette.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export interface BreakdownItem {
  prediction_type: string;
  count: number;
}

/** Split of predictions by task. */
export function PredictionTypeChart({
  data,
  height = 240,
}: {
  data: BreakdownItem[];
  height?: number;
}) {
  if (!data.length) {
    return (
      <div className="flex h-[240px] items-center justify-center text-sm text-muted-foreground">
        Nothing to chart yet.
      </div>
    );
  }

  const palette = ['#4ba148', '#bc8150', '#2f9e95', '#7c6bd6'];

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="prediction_type"
            innerRadius="52%"
            outerRadius="78%"
            paddingAngle={3}
            stroke="none"
          >
            {data.map((entry, index) => (
              <Cell key={entry.prediction_type} fill={palette[index % palette.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              border: '1px solid hsl(var(--border))',
              fontSize: 12,
            }}
          />
          <Legend
            verticalAlign="bottom"
            height={28}
            iconType="circle"
            wrapperStyle={{ fontSize: 12 }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export interface ConfidenceBarDatum {
  label: string;
  probability: number;
}

/** The top-k probabilities returned by the classifier. */
export function TopPredictionsChart({
  data,
  height = 220,
  className,
}: {
  data: ConfidenceBarDatum[];
  height?: number;
  className?: string;
}) {
  if (!data.length) {
    return (
      <div className={cn('flex items-center justify-center text-sm text-muted-foreground', className)}>
        No probability distribution available.
      </div>
    );
  }

  return (
    <div style={{ height }} className={cn('w-full', className)}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 24, left: 4, bottom: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 1]}
            tick={AXIS_STYLE}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: number) => `${Math.round(value * 100)}%`}
          />
          <YAxis
            type="category"
            dataKey="label"
            tick={AXIS_STYLE}
            tickLine={false}
            axisLine={false}
            width={160}
          />
          <Tooltip
            cursor={{ fill: 'hsl(var(--muted))' }}
            contentStyle={{
              borderRadius: 12,
              border: '1px solid hsl(var(--border))',
              fontSize: 12,
            }}
            formatter={(value: number) => [`${(value * 100).toFixed(2)}%`, 'Probability']}
          />
          <Bar dataKey="probability" radius={[0, 6, 6, 0]} barSize={16} fill="#4ba148" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export interface ForecastDatum {
  date: string;
  temperature_max: number;
  temperature_min: number;
  precipitation: number;
}

/** Daily temperature range for the forecast. */
export function ForecastChart({
  data,
  height = 260,
}: {
  data: ForecastDatum[];
  height?: number;
}) {
  if (!data.length) {
    return (
      <div className="flex h-[260px] items-center justify-center text-sm text-muted-foreground">
        No forecast available.
      </div>
    );
  }

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
          <XAxis dataKey="date" tick={AXIS_STYLE} tickLine={false} axisLine={false} minTickGap={20} />
          <YAxis tick={AXIS_STYLE} tickLine={false} axisLine={false} unit="°" />
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              border: '1px solid hsl(var(--border))',
              fontSize: 12,
            }}
            formatter={(value: number, name: string) => [`${value.toFixed(1)}°C`, name]}
          />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
          <Line
            type="monotone"
            dataKey="temperature_max"
            name="Max"
            stroke="#d98b3a"
            strokeWidth={2}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="temperature_min"
            name="Min"
            stroke="#2f9e95"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
