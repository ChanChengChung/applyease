import type { ReactElement } from "react";
import {
  render,
  type RenderOptions,
  type RenderResult,
} from "@testing-library/react";
import { LanguageProvider } from "../i18n/LanguageProvider";

// Wraps the standard RTL render with LanguageProvider so pages/components that
// call useT() work in tests. Default language is English (see i18n/index.ts).
export function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">,
): RenderResult {
  return render(<LanguageProvider>{ui}</LanguageProvider>, options);
}
