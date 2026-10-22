/** Disease detection endpoints. */

import { ApiError, api, queryString } from './api';
import type {
  DiseasePrediction,
  MessageResponse,
  PaginatedResponse,
  PredictionDetail,
  PredictionListItem,
} from '@/types';

export interface DiseaseHistoryQuery {
  page?: number;
  page_size?: number;
  prediction_type?: string;
  search?: string;
}

export const diseaseService = {
  /**
   * Upload a leaf image for classification.
   *
   * The file is sent as `multipart/form-data`; the browser sets the
   * `Content-Type` boundary itself, so the header must not be set manually.
   */
  predict: (file: File, onProgress?: (percent: number) => void) =>
    new Promise<DiseasePrediction>((resolve, reject) => {
      const form = new FormData();
      form.append('file', file);

      // `fetch` cannot report upload progress, so the progress callback is
      // driven by the request lifecycle instead of byte counts.
      onProgress?.(10);

      fetch(`${import.meta.env.VITE_API_BASE_URL ?? '/api/v1'}/disease/predict`, {
        method: 'POST',
        credentials: 'include',
        body: form,
        headers: csrfHeaders(),
      })
        .then(async (response) => {
          onProgress?.(70);
          if (!response.ok) {
            const text = await response.text();
            let detail = `The upload failed with status ${response.status}.`;
            let errorCode: string | null = null;
            try {
              const body = JSON.parse(text);
              detail = body.detail ?? detail;
              errorCode = body.error_code ?? null;
            } catch {
              /* keep the generic message */
            }
            reject(new ApiError(detail, response.status, errorCode));
            return;
          }
          return response.json();
        })
        .then((data) => {
          onProgress?.(100);
          resolve(data as DiseasePrediction);
        })
        .catch((error) => {
          onProgress?.(0);
          reject(error);
        });
    }),

  history: (query: DiseaseHistoryQuery = {}) =>
    api.get<PaginatedResponse<PredictionListItem>>(
      `/disease/history${queryString({
        page: query.page,
        page_size: query.page_size,
        prediction_type: query.prediction_type,
        search: query.search,
      })}`,
    ),

  detail: (id: string) => api.get<PredictionDetail>(`/disease/history/${id}`),

  remove: (id: string) => api.delete<MessageResponse>(`/disease/history/${id}`),
};

function csrfHeaders(): Record<string, string> {
  if (typeof document === 'undefined') return {};
  const match = document.cookie.match(
    /(?:^|;\s*)agrivision_csrf=([^;]*)/,
  );
  if (!match) return {};
  return { 'X-CSRF-Token': decodeURIComponent(match[1]) };
}
