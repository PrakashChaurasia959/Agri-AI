/** Unified prediction history (disease, crop recommendation and yield). */

import { api, queryString } from './api';
import type {
  MessageResponse,
  PaginatedResponse,
  PredictionDetail,
  PredictionListItem,
} from '@/types';

export interface HistoryQuery {
  page?: number;
  page_size?: number;
  prediction_type?: string;
  search?: string;
}

export const historyService = {
  list: (query: HistoryQuery = {}) =>
    api.get<PaginatedResponse<PredictionListItem>>(
      `/history${queryString({
        page: query.page,
        page_size: query.page_size,
        prediction_type: query.prediction_type,
        search: query.search,
      })}`,
    ),

  detail: (id: string) => api.get<PredictionDetail>(`/history/${id}`),

  remove: (id: string) => api.delete<MessageResponse>(`/history/${id}`),
};
