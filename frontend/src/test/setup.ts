import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(cleanup);

// Existing component/page tests assert Chinese UI strings. Mock detectLanguage
// to return Simplified Chinese so those assertions keep passing in the test
// environment. (The real default app language for users is English — see
// i18n/index.ts DEFAULT_LANGUAGE.)
vi.mock("../i18n/index", async () => {
  const actual =
    await vi.importActual<typeof import("../i18n/index")>("../i18n/index");

  return { ...actual, detectLanguage: () => "zh-CN" as const };
});
