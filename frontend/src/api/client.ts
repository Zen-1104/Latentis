/**
 * Typed fetch wrapper around the generated Phase 5 API contracts.
 *
 * Every response is the sealed envelope `{ data, meta }`. Errors are the
 * structured `{ error: { code, message, details, remediation, request_id } }`
 * contract (API_CONTRACT §9 / FR-603). This module never invents values:
 * transport failures and error envelopes surface as `ApiError` for the
 * UI's error/empty/degraded states — never as fake data.
 */
import type { Meta } from "./generated/client";

export interface ApiEnvelope<T> {
  data: T;
  meta: Meta;
}

export interface ApiErrorShape {
  code: string;
  message: string;
  details: unknown;
  remediation: string;
  requestId: string;
  status: number;
}

const BASE = "/api/v1";

export class ApiError extends Error {
  readonly code: string;
  readonly details: unknown;
  readonly remediation: string;
  readonly requestId: string;
  readonly status: number;

  constructor(shape: ApiErrorShape) {
    super(shape.message);
    this.name = "ApiError";
    this.code = shape.code;
    this.details = shape.details;
    this.remediation = shape.remediation;
    this.requestId = shape.requestId;
    this.status = shape.status;
  }

  /**
   * True only for "no dataset ingested yet" (fresh backend) → designed empty
   * state. Genuinely unknown resources ("Unknown lot 'X' in this dataset.")
   * stay errors. E2E-adversarial finding: code-only matching collapsed the
   * two cases and showed the ingest CTA for a typo'd lot id.
   */
  isNoDataset(): boolean {
    const knownCode =
      this.code === "UNKNOWN_LOT" ||
      this.code === "UNKNOWN_COMPONENT" ||
      this.code === "UNKNOWN_DATASET";
    return knownCode && /no dataset ingested yet/i.test(this.message);
  }
}

function toApiError(status: number, body: unknown, requestId: string): ApiError {
  if (body !== null && typeof body === "object" && "error" in body) {
    const err = (body as { error: Record<string, unknown> }).error;
    return new ApiError({
      code: typeof err["code"] === "string" ? err["code"] : "INTERNAL_ERROR",
      message: typeof err["message"] === "string" ? err["message"] : "Request failed.",
      details: err["details"] ?? null,
      remediation: typeof err["remediation"] === "string" ? err["remediation"] : "",
      requestId:
        typeof err["request_id"] === "string" ? (err["request_id"] as string) : requestId,
      status,
    });
  }
  // FastAPI request-validation errors: { detail: [{ loc, msg, type }] }
  if (body !== null && typeof body === "object" && "detail" in body) {
    return new ApiError({
      code: "VALIDATION_FAILED",
      message: "The request was rejected by input validation.",
      details: (body as { detail: unknown }).detail,
      remediation: "Check the path and parameters against GET /api/v1/openapi.json.",
      requestId,
      status,
    });
  }
  return new ApiError({
    code: status >= 500 ? "INTERNAL_ERROR" : "NOT_FOUND",
    message: `Request failed with status ${status}.`,
    details: null,
    remediation: "",
    requestId,
    status,
  });
}

async function request<T>(
  method: "GET" | "POST" | "PUT",
  path: string,
  body?: unknown,
  timeoutMs = 30000,
): Promise<ApiEnvelope<T>> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const headers: Record<string, string> = {};
  const init: RequestInit = { method, signal: controller.signal, headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  try {
    const response = await fetch(`${BASE}${path}`, init);
    const requestId = response.headers.get("X-Request-ID") ?? "unknown";
    let parsed: unknown = null;
    try {
      parsed = await response.json();
    } catch {
      parsed = null;
    }
    if (!response.ok) {
      throw toApiError(response.status, parsed, requestId);
    }
    const envelope = parsed as ApiEnvelope<T>;
    return { data: envelope.data, meta: envelope.meta };
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError({
        code: "TIMEOUT",
        message: `The request to ${path} timed out.`,
        details: null,
        remediation: "Retry. Lot-wide runs are batch operations and can take tens of seconds.",
        requestId: "unknown",
        status: 0,
      });
    }
    throw new ApiError({
      code: "NETWORK_UNREACHABLE",
      message: "The backend API is unreachable. Is it running on :8000?",
      details: null,
      remediation: "Start the backend, then retry. No data is shown until the API answers.",
      requestId: "unknown",
      status: 0,
    });
  } finally {
    clearTimeout(timer);
  }
}

export function apiGet<T>(path: string, timeoutMs?: number): Promise<ApiEnvelope<T>> {
  return request<T>("GET", path, undefined, timeoutMs);
}

export function apiPost<T>(path: string, body?: unknown, timeoutMs?: number): Promise<ApiEnvelope<T>> {
  return request<T>("POST", path, body, timeoutMs);
}

export function apiPut<T>(path: string, body?: unknown, timeoutMs?: number): Promise<ApiEnvelope<T>> {
  return request<T>("PUT", path, body, timeoutMs);
}
