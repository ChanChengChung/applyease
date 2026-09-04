import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError, request } from "./request";

describe("request", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("accepts a successful empty 204 response without parsing JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(request<void>("/jobs/42", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("hides technical server details from the UI-facing error message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "psycopg trace should not leak" }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(request("/materials/generate")).rejects.toMatchObject({
      message: "ApplyEase is temporarily unavailable. Please try again shortly.",
    } as Partial<ApiRequestError>);
  });
});
