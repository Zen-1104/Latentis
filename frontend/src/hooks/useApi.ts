import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, apiGet } from "../api/client";
import type { Meta } from "../api/generated/client";

export type ApiStatus = "loading" | "ready" | "empty" | "error";

export interface ApiResult<T> {
  status: ApiStatus;
  data: T | null;
  meta: Meta | null;
  error: ApiError | null;
  retry: () => void;
  /** True when the backend answered but no dataset is ingested (empty state, not error). */
  noDataset: boolean;
}

interface UseApiOptions<T> {
  timeoutMs?: number;
  /** Decide whether a successful payload counts as empty. */
  isEmpty?: (data: T) => boolean;
}

/**
 * Read-only data hook. GETs only — mutations use explicit event handlers so
 * no expensive lot run ever fires on page load.
 */
export function useApi<T>(path: string | null, options?: UseApiOptions<T>): ApiResult<T> {
  const [status, setStatus] = useState<ApiStatus>("loading");
  const [data, setData] = useState<T | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [nonce, setNonce] = useState(0);
  const timeoutMs = options?.timeoutMs;
  const isEmptyRef = useRef(options?.isEmpty);
  isEmptyRef.current = options?.isEmpty;

  const retry = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (path === null) {
      setStatus("loading");
      setData(null);
      setMeta(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setStatus("loading");
    setError(null);
    apiGet<T>(path, timeoutMs)
      .then((res) => {
        if (cancelled) return;
        setData(res.data);
        setMeta(res.meta);
        setStatus(isEmptyRef.current?.(res.data) === true ? "empty" : "ready");
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const apiErr =
          err instanceof ApiError
            ? err
            : new ApiError({
                code: "INTERNAL_ERROR",
                message: "Unexpected fetch failure.",
                details: null,
                remediation: "",
                requestId: "unknown",
                status: 0,
              });
        // "No dataset ingested" is an expected empty state, not a failure.
        if (apiErr.isNoDataset()) {
          setStatus("empty");
          setData(null);
          setMeta(null);
          setError(apiErr);
          return;
        }
        setStatus("error");
        setError(apiErr);
      });
    return () => {
      cancelled = true;
    };
  }, [path, nonce, timeoutMs]);

  return { status, data, meta, error, retry, noDataset: status === "empty" };
}
