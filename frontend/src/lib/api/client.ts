import createClient from "openapi-fetch";

import type { paths } from "./schema";

/** Browser-visible URL of the FastAPI backend. */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const api = createClient<paths>({ baseUrl: API_URL, credentials: "include" });

interface ErrorEnvelope {
  error: { code: string; message: string; details?: unknown };
}

/** A failed API call, carrying the server's stable error code. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function isEnvelope(value: unknown): value is ErrorEnvelope {
  return typeof value === "object" && value !== null && "error" in value;
}

/** Turn an openapi-fetch result into its data or throw an {@link ApiError}. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    const { error, response } = result;
    if (isEnvelope(error)) {
      throw new ApiError(
        response.status,
        error.error.code,
        error.error.message,
        error.error.details,
      );
    }
    throw new ApiError(
      response.status,
      "http_error",
      `Request failed (${String(response.status)})`,
    );
  }
  return result.data;
}

/** Wrap network failures (server down) as ApiError so the UI shows one consistent message. */
export async function call<T>(
  request: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  try {
    return unwrap(await request);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      0,
      "network_error",
      "Cannot reach the server. Check your connection and retry.",
    );
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong";
}
