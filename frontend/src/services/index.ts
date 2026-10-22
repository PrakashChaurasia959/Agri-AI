/** Dashboard, weather, system and admin endpoints. */

import { api, queryString } from './api';
import type {
  AdminActivityItem,
  AdminAnalytics,
  AdminStats,
  AdminUser,
  CurrentWeatherResponse,
  DashboardAnalytics,
  DashboardOverviewResponse,
  ForecastResponse,
  HealthResponse,
  MessageResponse,
  ModelStatusResponse,
  PaginatedResponse,
  WeatherLocation,
} from '@/types';

export const dashboardService = {
  overview: () => api.get<DashboardOverviewResponse>('/dashboard/overview'),
  analytics: (days = 30) =>
    api.get<DashboardAnalytics>(`/dashboard/analytics${queryString({ days })}`),
};

export const weatherService = {
  search: (query: string) =>
    api.get<WeatherLocation[]>(`/weather/search${queryString({ query })}`),

  current: (latitude: number, longitude: number, locationName?: string) =>
    api.get<CurrentWeatherResponse>(
      `/weather/current${queryString({
        latitude,
        longitude,
        location_name: locationName,
      })}`,
    ),

  forecast: (latitude: number, longitude: number, days = 7, locationName?: string) =>
    api.get<ForecastResponse>(
      `/weather/forecast${queryString({
        latitude,
        longitude,
        days,
        location_name: locationName,
      })}`,
    ),
};

export const systemService = {
  health: () => api.get<HealthResponse>('/health'),
  models: () => api.get<ModelStatusResponse>('/models/status'),
};

export const adminService = {
  users: (
    query: { page?: number; page_size?: number; search?: string; role?: string } = {},
  ) =>
    api.get<PaginatedResponse<AdminUser>>(
      `/admin/users${queryString({
        page: query.page,
        page_size: query.page_size,
        search: query.search,
        role: query.role,
      })}`,
    ),

  user: (id: string) => api.get<AdminUser>(`/admin/users/${id}`),

  setRole: (id: string, role: 'user' | 'admin') =>
    api.patch<AdminUser>(`/admin/users/${id}/role${queryString({ role })}`),

  remove: (id: string) =>
    api.delete<MessageResponse>(`/admin/users/${id}`),

  stats: () => api.get<AdminStats>('/admin/stats'),

  analytics: () => api.get<AdminAnalytics>('/admin/analytics'),

  activity: (query: { page?: number; page_size?: number; action?: string } = {}) =>
    api.get<PaginatedResponse<AdminActivityItem>>(
      `/admin/activity${queryString({
        page: query.page,
        page_size: query.page_size,
        action: query.action,
      })}`,
    ),

  models: () => api.get<ModelStatusResponse>('/admin/models'),
};
