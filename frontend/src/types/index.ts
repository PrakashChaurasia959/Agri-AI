/**
 * Type definitions that mirror the AgriVision AI backend schemas.
 *
 * These are hand-written rather than generated so that the frontend stays
 * buildable without the backend running, but every field name and nullability
 * matches the Pydantic models in `backend/app/schemas`.
 */

/* -------------------------------------------------------------------------- */
/* Authentication                                                              */
/* -------------------------------------------------------------------------- */

export type UserRole = 'user' | 'admin';

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  location: string | null;
  farm_size_hectares: number | null;
  primary_crops: string[];
  created_at: string | null;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  csrf_token: string | null;
  user: User;
}

export interface RegisterPayload {
  name: string;
  email: string;
  password: string;
  location?: string | null;
  primary_crops?: string[];
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface UpdateProfilePayload {
  name?: string;
  location?: string | null;
  farm_size_hectares?: number | null;
  primary_crops?: string[];
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
}

/* -------------------------------------------------------------------------- */
/* Shared envelope                                                            */
/* -------------------------------------------------------------------------- */

export interface MessageResponse {
  message: string;
  success: boolean;
}

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  pagination: PaginationMeta;
}

export interface ApiErrorBody {
  detail: string;
  error_code?: string | null;
  field_errors?: Record<string, string> | null;
}

/* -------------------------------------------------------------------------- */
/* Disease detection                                                          */
/* -------------------------------------------------------------------------- */

export interface DiseaseInfo {
  crop: string | null;
  symptoms: string[];
  prevention: string[];
  treatment: string[];
  severity: string | null;
  disclaimer: string | null;
}

export interface TopPrediction {
  label: string;
  probability: number;
}

/** The backend returns the image metadata as a flat dictionary. */
export type ImageMetadata = Record<string, string | number | null>;

export interface DiseasePrediction {
  prediction_id: string | null;
  predicted_class: string;
  display_name: string;
  confidence: number;
  confidence_percent: number;
  is_healthy: boolean;
  is_certain: boolean;
  uncertainty_message: string | null;
  model_name: string;
  model_version: string;
  inference_ms: number;
  top_predictions: TopPrediction[];
  disease_info: DiseaseInfo | null;
  image: ImageMetadata;
  saved: boolean;
  created_at: string | null;
}

export interface PredictionListItem {
  id: string;
  prediction_type: string;
  predicted_class: string;
  /** Null for a yield estimate, which has no class probability. */
  confidence: number | null;
  model_name: string;
  model_version: string;
  created_at: string;
  input_summary: Record<string, unknown>;
}

export interface PredictionDetail extends PredictionListItem {
  details: Record<string, unknown>;
  image_metadata: ImageMetadata;
}

/* -------------------------------------------------------------------------- */
/* Crop recommendation                                                        */
/* -------------------------------------------------------------------------- */

export interface CropRecommendationItem {
  crop: string;
  score: number;
  rank: number;
}

export interface CropRecommendation {
  record_id: string | null;
  recommendations: CropRecommendationItem[];
  top_crop: string | null;
  top_score: number | null;
  input_summary: Record<string, unknown>;
  explanation: string[];
  model_name: string;
  model_version: string;
  metrics: Record<string, number>;
  disclaimer: string;
  created_at: string | null;
}

export interface CropRecordListItem {
  id: string;
  crop_type: string;
  soil_parameters: Record<string, unknown>;
  environmental_parameters: Record<string, unknown>;
  prediction_summary: Record<string, unknown>;
  created_at: string;
}

/* -------------------------------------------------------------------------- */
/* Yield estimation                                                           */
/* -------------------------------------------------------------------------- */

export interface YieldPrediction {
  record_id: string | null;
  crop_type: string;
  estimated_yield: number | null;
  yield_unit: string;
  per_hectare_yield: number | null;
  confidence_interval: [number, number] | null;
  model_name: string;
  model_version: string;
  metrics: Record<string, number>;
  input_summary: Record<string, unknown>;
  disclaimer: string;
  available: boolean;
  created_at: string | null;
}

/* -------------------------------------------------------------------------- */
/* Dashboard                                                                  */
/* -------------------------------------------------------------------------- */

export interface DashboardOverview {
  total_predictions: number;
  disease_predictions: number;
  crop_recommendations: number;
  yield_predictions: number;
  healthy_leaves: number;
  affected_leaves: number;
  saved_reports: number;
  distinct_crops_recommended: number;
  average_confidence: number | null;
  first_prediction_at: string | null;
  last_prediction_at: string | null;
}

export interface RecentActivity {
  id: string;
  prediction_type: string;
  predicted_class: string;
  /** Null for a yield estimate, which has no class probability. */
  confidence: number | null;
  created_at: string;
}

export interface DashboardOverviewResponse {
  user: User;
  overview: DashboardOverview;
  recent_predictions: RecentActivity[];
  top_crop_recommendations: Record<string, unknown>[];
  model_status: Record<string, unknown>[];
  database_connected: boolean;
  generated_at: string;
}

export interface TrendPoint {
  date: string;
  value: number;
}

export interface ConfidenceBucket {
  label: string;
  value: number;
}

export interface TypeBreakdownItem {
  type: string;
  label: string;
  value: number;
}

export interface CropDistributionItem {
  crop: string;
  value: number;
}

export interface DashboardAnalytics {
  daily_predictions: TrendPoint[];
  prediction_type_breakdown: TypeBreakdownItem[];
  confidence_buckets: ConfidenceBucket[];
  crop_distribution: CropDistributionItem[];
  total_records: number;
  window_days: number;
}

/* -------------------------------------------------------------------------- */
/* Weather                                                                    */
/* -------------------------------------------------------------------------- */

export interface WeatherLocation {
  name: string;
  latitude: number;
  longitude: number;
  country: string | null;
  admin1: string | null;
  timezone: string | null;
}

export interface CurrentWeather {
  temperature: number | null;
  apparent_temperature: number | null;
  humidity: number | null;
  precipitation: number | null;
  rainfall: number | null;
  wind_speed: number | null;
  wind_direction: number | null;
  weather_code: number | null;
  weather_description: string | null;
  is_day: boolean | null;
  cloud_cover: number | null;
  surface_pressure: number | null;
  observed_at: string | null;
}

export interface CurrentWeatherResponse {
  location: WeatherLocation;
  current: CurrentWeather;
  source: string;
  fetched_at: string;
}

export interface DailyForecastEntry {
  date: string;
  temperature_max: number | null;
  temperature_min: number | null;
  precipitation_sum: number | null;
  precipitation_probability_max: number | null;
  wind_speed_max: number | null;
  weather_code: number | null;
  weather_description: string | null;
}

export interface ForecastResponse {
  location: WeatherLocation;
  daily: DailyForecastEntry[];
  hourly: Record<string, unknown>[];
  source: string;
  fetched_at: string;
}

/* -------------------------------------------------------------------------- */
/* Models & system                                                            */
/* -------------------------------------------------------------------------- */

export interface ModelStatus {
  key: string;
  display_name: string;
  task: string;
  available: boolean;
  model_name: string | null;
  model_version: string | null;
  accuracy: number | null;
  metrics: Record<string, number>;
  classes_count: number | null;
  trained_at: string | null;
  dataset: string | null;
  message: string | null;
  artifact_path: string | null;
}

export interface ModelStatusResponse {
  available_count: number;
  total_count: number;
  models: ModelStatus[];
  model_dir: string;
  device: string;
  note: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  database: string;
  database_message: string | null;
  models: {
    available: number;
    total: number;
    detail: Record<string, boolean>;
  };
  server_time: string;
}

/* -------------------------------------------------------------------------- */
/* Admin                                                                      */
/* -------------------------------------------------------------------------- */

export interface AdminUser extends User {
  total_predictions: number;
  last_prediction_at: string | null;
}

export interface AdminStats {
  total_users: number;
  total_predictions: number;
  disease_predictions: number;
  crop_recommendations: number;
  yield_predictions: number;
  saved_reports: number;
  healthy_leaves: number;
  affected_leaves: number;
  new_users_7d: number;
  predictions_7d: number;
}

export interface AdminActivityItem {
  id: string;
  actor_email: string | null;
  action: string;
  target_type: string | null;
  created_at: string;
  ip_address: string | null;
}

export interface AdminAnalytics {
  prediction_type_breakdown: Array<{ type: string | null; value: number }>;
  top_disease_classes: Array<{ label: string; count: number }>;
  distinct_classes: number;
  generated_at: string;
}
