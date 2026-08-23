import { detectFields } from "../fieldDetector";
import type { SiteAdapter } from "./types";
import { greenhouseAdapter } from "./greenhouseAdapter";
import { leverAdapter } from "./leverAdapter";

const genericAdapter: SiteAdapter = { name: "generic", matches: () => true, detectFields };

export function selectSiteAdapter(documentRoot: Document, location?: Location): SiteAdapter {
  if (greenhouseAdapter.matches(documentRoot, location)) return greenhouseAdapter;
  if (leverAdapter.matches(documentRoot, location)) return leverAdapter;
  return genericAdapter;
}
