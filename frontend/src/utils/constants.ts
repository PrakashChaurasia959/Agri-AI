/** Shared constants: navigation, crop lists, weather codes. */

import {
  BarChart3,
  CloudSun,
  LayoutDashboard,
  Leaf,
  Shield,
  Sprout,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react';

export interface NavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  description: string;
  adminOnly?: boolean;
}

export const PRIMARY_NAV: NavItem[] = [
  {
    label: 'Dashboard',
    to: '/dashboard',
    icon: LayoutDashboard,
    description: 'Your farm activity at a glance',
  },
  {
    label: 'Disease Detection',
    to: '/disease',
    icon: Leaf,
    description: 'Classify a leaf from a photo',
  },
  {
    label: 'Crop Recommendation',
    to: '/crops',
    icon: Sprout,
    description: 'Match soil and climate to a crop',
  },
  {
    label: 'Yield Estimation',
    to: '/yield',
    icon: TrendingUp,
    description: 'Estimate the harvest in tonnes',
  },
  {
    label: 'Weather',
    to: '/weather',
    icon: CloudSun,
    description: 'Local forecast for your fields',
  },
  {
    label: 'History',
    to: '/history',
    icon: BarChart3,
    description: 'Every prediction you have made',
  },
];

export const ADMIN_NAV: NavItem[] = [
  {
    label: 'Administration',
    to: '/admin',
    icon: Shield,
    description: 'Manage users, models and activity',
    adminOnly: true,
  },
];

/** The 22 crops the recommendation model can output. */
export const SUPPORTED_CROPS = [
  'apple',
  'banana',
  'barley',
  'black gram',
  'chickpeas',
  'cocoa beans',
  'coffee',
  'corn',
  'cotton',
  'grapes',
  'groundnut',
  'kidney beans',
  'lentils',
  'maize',
  'mango',
  'millet',
  'mung beans',
  'mustard',
  'orange',
  'papaya',
  'pigeon peas',
  'rice',
  'sorghum',
  'soybeans',
  'sugarcane',
  'wheat',
] as const;

export type SupportedCrop = (typeof SUPPORTED_CROPS)[number];

/** WMO weather interpretation codes used by the backend. */
export const WEATHER_CODES: Record<number, { label: string; icon: string }> = {
  0: { label: 'Clear sky', icon: 'sun' },
  1: { label: 'Mainly clear', icon: 'sun' },
  2: { label: 'Partly cloudy', icon: 'cloud-sun' },
  3: { label: 'Overcast', icon: 'cloud' },
  45: { label: 'Fog', icon: 'cloud-fog' },
  48: { label: 'Depositing rime fog', icon: 'cloud-fog' },
  51: { label: 'Light drizzle', icon: 'cloud-drizzle' },
  53: { label: 'Moderate drizzle', icon: 'cloud-drizzle' },
  55: { label: 'Dense drizzle', icon: 'cloud-drizzle' },
  56: { label: 'Light freezing drizzle', icon: 'cloud-drizzle' },
  57: { label: 'Dense freezing drizzle', icon: 'cloud-drizzle' },
  61: { label: 'Slight rain', icon: 'cloud-rain' },
  63: { label: 'Moderate rain', icon: 'cloud-rain' },
  65: { label: 'Heavy rain', icon: 'cloud-rain' },
  66: { label: 'Light freezing rain', icon: 'cloud-rain' },
  67: { label: 'Heavy freezing rain', icon: 'cloud-rain' },
  71: { label: 'Slight snow fall', icon: 'snowflake' },
  73: { label: 'Moderate snow fall', icon: 'snowflake' },
  75: { label: 'Heavy snow fall', icon: 'snowflake' },
  77: { label: 'Snow grains', icon: 'snowflake' },
  80: { label: 'Slight rain showers', icon: 'cloud-rain-wind' },
  81: { label: 'Moderate rain showers', icon: 'cloud-rain-wind' },
  82: { label: 'Violent rain showers', icon: 'cloud-rain-wind' },
  85: { label: 'Slight snow showers', icon: 'snowflake' },
  86: { label: 'Heavy snow showers', icon: 'snowflake' },
  95: { label: 'Thunderstorm', icon: 'cloud-lightning' },
  96: { label: 'Thunderstorm with slight hail', icon: 'cloud-lightning' },
  99: { label: 'Thunderstorm with heavy hail', icon: 'cloud-lightning' },
};

export const SOIL_TYPES = [
  'sandy',
  'loamy',
  'clayey',
  'silty',
  'red',
  'black',
  'alluvial',
  'laterite',
] as const;

export const MAX_UPLOAD_MB = 10;
export const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
