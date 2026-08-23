import { afterEach, describe, expect, it, vi } from "vitest";
import { request } from "./request";

describe("request", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("accepts a successful empty 204 response without parsing JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(request<void>("/jobs/42", { method: "DELETE" })).resolves.toBeUndefined();
  });
});
