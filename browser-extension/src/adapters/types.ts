import type { DetectedField } from "../types";

export interface SiteAdapter {
  readonly name: string;
  matches(documentRoot: Document, location?: Location): boolean;
  detectFields(documentRoot: Document): DetectedField[];
}
