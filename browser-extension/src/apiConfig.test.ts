import { describe, expect, it } from "vitest";
import { API_ACCESS_TOKEN_KEY, API_BASE_URL_KEY, apiOriginPattern, DEFAULT_API_BASE_URL, getApiBaseUrl, getAuthHeaders, normalizeApiBaseUrl, saveApiBaseUrl } from "./apiConfig";

describe("apiConfig", () => {
  it("normalizes the base address and removes an accidental API suffix", () => {
    expect(normalizeApiBaseUrl(" http://localhost:8000/api/v1/ ")).toBe("http://localhost:8000");
    expect(apiOriginPattern("https://api.example.com/applyease")).toBe("https://api.example.com/*");
  });
  it("rejects unsafe or malformed addresses", () => {
    expect(() => normalizeApiBaseUrl("file:///tmp/api")).toThrow(/HTTP/);
    expect(() => normalizeApiBaseUrl("https://user:secret@example.com")).toThrow(/用户名/);
    expect(() => normalizeApiBaseUrl("not a url")).toThrow(/格式/);
    expect(() => normalizeApiBaseUrl("http://api.example.com")).toThrow(/HTTPS/);
  });
  it("uses the default when storage is empty", async () => {
    await expect(getApiBaseUrl({ get: async () => ({}) })).resolves.toBe(DEFAULT_API_BASE_URL);
  });
  it("builds a bearer header without exposing an empty token", async () => {
    await expect(getAuthHeaders({ get: async () => ({ [API_ACCESS_TOKEN_KEY]: "signed-token" }) })).resolves.toEqual({ Authorization: "Bearer signed-token" });
    await expect(getAuthHeaders({ get: async () => ({}) })).resolves.toEqual({});
  });
  it("clears a prior bearer token when the backend address changes", async () => {
    const calls: string[] = [];
    const storage = {
      set: async (values: Record<string, string>) => { expect(values).toEqual({ [API_BASE_URL_KEY]: "https://api.example.com" }); },
      remove: async (key: string) => { calls.push(key); },
    };
    await expect(saveApiBaseUrl(storage, "https://api.example.com/api/v1")).resolves.toBe("https://api.example.com");
    expect(calls).toEqual([API_ACCESS_TOKEN_KEY]);
  });
});
