import { describe, expect, it } from "vitest";
import { detectContentLanguage } from "./contentLanguage";

describe("detectContentLanguage", () => {
  it("detects English independently of the UI locale", () => {
    expect(detectContentLanguage("I am a first-year student interested in writing")).toBe("en");
  });

  it("distinguishes Simplified and Traditional Chinese", () => {
    expect(detectContentLanguage("我是大一学生，对数学很感兴趣")).toBe("zh-CN");
    expect(detectContentLanguage("我是大一學生，對數學很感興趣")).toBe("zh-TW");
  });

  it("defaults ambiguous Chinese characters to Simplified Chinese", () => {
    expect(detectContentLanguage("数学")).toBe("zh-CN");
  });
});
