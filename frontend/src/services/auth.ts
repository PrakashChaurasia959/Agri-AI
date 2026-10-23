/** Authentication, session and profile endpoints. */

import { api } from './api';
import type {
  ChangePasswordPayload,
  LoginPayload,
  MessageResponse,
  RegisterPayload,
  TokenResponse,
  UpdateProfilePayload,
  User,
} from '@/types';

export const authService = {
  register: (payload: RegisterPayload) =>
    api.post<TokenResponse>('/auth/register', payload),

  login: (payload: LoginPayload) => api.post<TokenResponse>('/auth/login', payload),

  /** Silently exchanges the refresh cookie for a new access token. */
  refresh: () =>
    api.post<TokenResponse>('/auth/refresh', undefined, { skipRefresh: true }),

  logout: () => api.post<MessageResponse>('/auth/logout'),

  me: () => api.get<User>('/auth/me'),

  updateProfile: (payload: UpdateProfilePayload) =>
    api.patch<User>('/auth/me', payload),

  changePassword: (payload: ChangePasswordPayload) =>
    api.post<MessageResponse>('/auth/change-password', payload),

  forgotPassword: (email: string) =>
    api.post<MessageResponse>('/auth/forgot-password', { email }),

  resetPassword: (payload: { token: string; password: string }) =>
    api.post<MessageResponse>('/auth/reset-password', payload),
};
