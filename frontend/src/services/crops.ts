/** Crop recommendation, crop history and yield estimation endpoints. */

import { api, queryString } from './api';
import type {
  CropRecommendation,
  CropRecordListItem,
  PaginatedResponse,
  YieldPrediction,
} from '@/types';

export interface CropRecommendationPayload {
  nitrogen: number;
  phosphorus: number;
  potassium: number;
  temperature: number;
  humidity: number;
  rainfall: number;
  ph: number;
  soil_type?: string | null;
  location?: string | null;
}

export interface YieldPayload {
  crop_type: string;
  nitrogen: number;
  phosphorus: number;
  potassium: number;
  temperature: number;
  humidity: number;
  rainfall: number;
  ph: number;
  area_ha: number;
}

export const cropService = {
  recommend: (payload: CropRecommendationPayload) =>
    api.post<CropRecommendation>('/crops/recommend', payload),

  history: (query: { page?: number; page_size?: number } = {}) =>
    api.get<PaginatedResponse<CropRecordListItem>>(
      `/crops/history${queryString({
        page: query.page,
        page_size: query.page_size,
      })}`,
    ),
};

export const yieldService = {
  predict: (payload: YieldPayload) =>
    api.post<YieldPrediction>('/yield/predict', payload),
};
