// Centralized fetch helper shared by every service module.
//
// It replaces the repeated boilerplate that used to live in each *Api.ts file:
//   const response = await fetch(...);
//   if (!response.ok) { const e = await response.json().catch(() => ({})); throw new Error(e.detail || "中文"); }
//   return response.json();
//
// Responsibilities:
//   1. Resolve the API base URL (env override -> localhost default).
//   2. Perform the fetch with the provided init.
//   3. On a non-OK status, throw an ApiRequestError whose `detail` carries the
//      backend's `detail` message (when present) and whose `status` is the HTTP code.
//      NOTE: we deliberately do NOT bake any human-language fallback text here —
//      the caller / UI is responsible for localizing the message (see i18n).
//   4. Parse and return the JSON body typed as T.

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

/** Error thrown by {@link request} when the response status is not OK. */
export class ApiRequestError extends Error {
  /** HTTP status code returned by the server. */
  status: number;
  /** Backend-provided `detail` message, if the response body included one. */
  detail?: string;

  constructor(status: number, detail?: string) {
    // Message is intentionally language-neutral (status + detail only).
    super(
      detail
        ? `Request failed (${status}): ${detail}`
        : `Request failed (${status})`,
    );
    this.name = "ApiRequestError";
    this.status = status;
    this.detail = detail;
  }
}

/** Shape of a typical FastAPI error response body. */
type ErrorBody = { detail?: string };

/**
 * Perform a fetch against the API and return the parsed JSON body.
 *
 * @param path   Absolute (https://...) or relative (resolved against API base) URL.
 * @param init   Standard RequestInit (method, headers, body, signal, ...).
 * @param opts   `expectStatus` allows treating a specific non-2xx status as success
 *               (e.g. 401 => null for "session not found"). `parseJson: false` skips
 *               JSON parsing and returns undefined (useful for empty 204 responses).
 */
export async function request<T>(
  path: string,
  init: RequestInit = {},
  opts: { expectStatus?: number; parseJson?: boolean } = {},
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API}${path}`;
  const response = await fetch(url, init);

  // Caller may treat a specific status (e.g. 401) as a non-error sentinel.
  if (
    opts.expectStatus !== undefined &&
    response.status === opts.expectStatus
  ) {
    return undefined as T;
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}) as ErrorBody);
    throw new ApiRequestError(response.status, body.detail);
  }

  // A successful DELETE commonly responds with FastAPI's 204 No Content.
  // Treat every empty success as ``undefined`` instead of attempting
  // Response.json(), which would otherwise throw after the mutation succeeded.
  if (opts.parseJson === false || response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
