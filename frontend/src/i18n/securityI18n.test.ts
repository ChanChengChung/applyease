import { describe, expect, it } from "vitest";
import { translate, type Language } from "./index";

describe("Security page translations", () => {
  it("provides non-fallback copy for every supported language", () => {
    const keys = [
      "security.hero.title",
      "security.changePassword",
      "security.downloadData",
      "security.deletePermanently",
      "security.mfa",
      "security.recoveryDescription",
    ];
    for (const language of ["en", "zh-CN", "zh-TW"] as Language[]) {
      for (const key of keys) expect(translate(language, key)).not.toBe(key);
    }
  });
});
