/** A small `useAsync` hook for data fetching with loading/error state. */

import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError } from '@/services/api';

export interface AsyncState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
  reload: () => void;
  setData: (value: T | null) => void;
}

export function useAsync<T>(
  loader: () => Promise<T>,
  deps: unknown[] = [],
  options: { enabled?: boolean } = {},
): AsyncState<T> {
  const { enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const mounted = useRef(true);
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false);
      return;
    }
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    loaderRef
      .current()
      .then((result) => {
        if (!cancelled && mounted.current) setData(result);
      })
      .catch((caught: unknown) => {
        if (cancelled || !mounted.current) return;
        if (caught instanceof ApiError) {
          setError(caught.message);
        } else if (caught instanceof Error) {
          setError(caught.message);
        } else {
          setError('Something went wrong while loading the data.');
        }
      })
      .finally(() => {
        if (!cancelled && mounted.current) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, nonce, ...deps]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);
  const update = useCallback((value: T | null) => setData(value), []);

  return { data, isLoading, error, reload, setData: update };
}
