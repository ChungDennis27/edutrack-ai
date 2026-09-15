/**
 * Shared API client.
 *
 * Auth uses JWT stored in httpOnly cookies, so every request must send
 * credentials. Because the backend enables CSRF protection for cookie-based
 * JWTs, all state-changing requests must echo the readable `csrf_access_token`
 * cookie back in the `X-CSRF-TOKEN` header (double-submit pattern).
 */

const CSRF_COOKIE_NAME = "csrf_access_token";
const CSRF_HEADER_NAME = "X-CSRF-TOKEN";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function readCookie(name: string): string | null {
  const match = document.cookie.match(
    new RegExp("(?:^|;\\s*)" + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "=([^;]*)")
  );
  return match ? decodeURIComponent(match[1]) : null;
}

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object") {
    const maybe = payload as Record<string, unknown>;
    if (typeof maybe.error === "string" && maybe.error) return maybe.error;
    if (typeof maybe.message === "string" && maybe.message) return maybe.message;
  }
  return fallback;
}

export interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  /** Plain object is serialised to JSON automatically. */
  body?: unknown;
}

export async function apiRequest(
  path: string,
  options: ApiRequestOptions = {}
): Promise<Response> {
  const { body: rawBody, headers: initHeaders, ...rest } = options;
  const method = (rest.method ?? "GET").toUpperCase();

  const headers = new Headers(initHeaders);
  let body: BodyInit | undefined;

  if (rawBody !== undefined && rawBody !== null) {
    if (
      rawBody instanceof FormData ||
      rawBody instanceof Blob ||
      typeof rawBody === "string"
    ) {
      body = rawBody;
    } else {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(rawBody);
    }
  }

  if (!SAFE_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) headers.set(CSRF_HEADER_NAME, csrfToken);
  }

  return fetch(path, {
    credentials: "include",
    ...rest,
    method,
    headers,
    body,
  });
}

/** Performs a request and throws `ApiError` on non-2xx responses. */
export async function apiJson<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const res = await apiRequest(path, options);
  const isJson = res.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await res.json() : await res.text().catch(() => null);

  if (!res.ok) {
    throw new ApiError(
      extractErrorMessage(payload, `請求失敗（HTTP ${res.status}）`),
      res.status,
      payload
    );
  }

  return payload as T;
}
