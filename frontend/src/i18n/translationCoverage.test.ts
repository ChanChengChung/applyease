import { describe, expect, it } from "vitest";
import { missingTranslationKeys } from "./index";

describe("translation coverage", () => {
  it("keeps Simplified Chinese aligned with the English reference keys", () => {
    expect(missingTranslationKeys("zh-CN")).toEqual([]);
  });

  it("keeps Traditional Chinese aligned with the English reference keys", () => {
    expect(missingTranslationKeys("zh-TW")).toEqual([]);
  });
});
