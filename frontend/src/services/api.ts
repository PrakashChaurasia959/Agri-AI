/**
 * The single HTTP entry point for the whole application.
 *
 * Authentication strategy
 * ------------------------
 * The backend issues the access token as an **HttpOnly** cookie, so
 * JavaScript can never read it and an XSS bug cannot exfiltrate the
 * session.  Because the browser attaches that cookie automatically, every
 * state-changing request must also carry a **double-submit CSRF token**:
 * the backend sets a readable `agrivision_csrf` cookie and expects it to be
 * echoed back in the `X-CSRF-Token` header.
 *
 * `Authorization: Bearer` is still supported by the backend for scripted
 * clients, but the browser app never uses it - the cookie flow is strictly
 * safer and the CSRF header is the only extra cost.
 */

import type { ApiErrorBody } from '@/types';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(
  /\/$/,
  '',
);

const CSRF_COOKIE_NAME = 'agrivision_csrf';
const CSRF_HEADER_NAME = 'X-CSRF-Token';

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

export class ApiError extends Error {
  readonly status: number;
  readonly errorCode: string | null;
  readonly fieldErrors: Record<string, string>;
  readonly body: ApiErrorBody | null;

  constructor(
    message: string,
    status: number,
    errorCode: string | null = null,
    fieldErrors: Record<string, string> = {},
    body: ApiErrorBody | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errorCode = errorCode;
    this.fieldErrors = fieldErrors;
    this.body = body;
  }

  /** True when the request failed because the server has no data store. */
  get isDatabaseUnavailable(): boolean {
    return this.status === 503;
  }

  /** True when the request failed because a model artifact is missing. */
  get isModelUnavailable(): boolean {
    return this.status === 503;
  }

  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isValidationError(): boolean {
    return this.status === 422 || this.status === 400;
  }
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(
    new RegExp(`(?:^|;\\s*)${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}=([^;]*)`),
  );
  return match ? decodeURIComponent(match[1]) : null;
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  /** JSON body - serialised automatically. */
  json?: unknown;
  /** Pre-built body (used for multipart uploads). */
  body?: BodyInit | null;
  /** Do not attempt an automatic token refresh on 401. */
  skipRefresh?: boolean;
  /** Number of times the request may be retried after a refresh. */
  retries?: number;
}

let refreshInFlight: Promise<boolean> | null = null;

/**
 * Refresh the session once, even if several requests fail at the same time.
 */
async function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
        });
        return response.ok;
      } catch {
        return false;
      } finally {
        // Release the lock on the next tick so the awaiting callers see the
        // result before the promise is discarded.
        setTimeout(() => {
          refreshInFlight = null;
        }, 0);
      }
    })();
  }
  return refreshInFlight;
}

async function parseError(response: Response): Promise<ApiError> {
  let body: ApiErrorBody | null = null;
  try {
    const text = await response.text();
    if (text) {
      body = JSON.parse(text) as ApiErrorBody;
    }
  } catch {
    body = null;
  }

  const detail =
    body?.detail ??
    (response.status === 404
      ? 'The requested resource was not found.'
      : `The request failed with status ${response.status}.`);

  return new ApiError(
    detail,
    response.status,
    body?.error_code ?? null,
    body?.field_errors ?? {},
    body,
  );
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { json, body, skipRefresh, retries = 1, headers, ...rest } = options;
  const method = (rest.method ?? 'GET').toUpperCase();

  const finalHeaders = new Headers(headers);
  if (json !== undefined) {
    finalHeaders.set('Content-Type', 'application/json');
  }

  // Double-submit CSRF token for every state-changing request.
  if (!SAFE_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) {
      finalHeaders.set(CSRF_HEADER_NAME, csrfToken);
    }
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    method,
    headers: finalHeaders,
    credentials: 'include',
    body: json !== undefined ? JSON.stringify(json) : body,
  });

  if (response.status === 401 && !skipRefresh && retries > 0) {
    const refreshed = await refreshSession();
    if (refreshed) {
      return apiRequest<T>(path, { ...options, skipRefresh: true, retries: retries - 1 });
    }
  }

  if (!response.ok) {
    throw await parseError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    return (await response.text()) as unknown as T;
  }

  return (await response.json()) as T;
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'POST', json }),
  patch: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'PATCH', json }),
  put: <T>(path: string, json?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'PUT', json }),
  delete: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'DELETE' }),
};

/** Build a query string, skipping empty / undefined values. */
export function queryString(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    search.set(key, String(value));
  });
  const result = search.toString();
  return result ? `?${result}` : '';
}
