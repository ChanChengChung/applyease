import { afterEach, describe, expect, it } from "vitest";
import { saveLanguage } from "./index";

describe("language URL paths", () => {
  afterEach(() => window.history.replaceState({}, "", "/"));

  it("writes a canonical shareable path and preserves the query and hash", () => {
    window.history.replaceState({}, "", "/jobs?source=sidebar#report");
    saveLanguage("zh-TW");
    expect(window.location.pathname).toBe("/zh-tw/jobs");
    expect(window.location.search).toBe("?source=sidebar");
    expect(window.location.hash).toBe("#report");
  });

  it("replaces an existing language path instead of nesting it", () => {
    window.history.replaceState({}, "", "/zh-tw/security");
    saveLanguage("en");
    expect(window.location.pathname).toBe("/en/security");
  });
});
