declare const chrome: any;
import { selectSiteAdapter } from "./adapters";
import { fillFields } from "./fillController";

chrome.runtime.onMessage.addListener((message: { type: string; items?: Array<{ field_id: string; answer: string }> }, _sender: unknown, sendResponse: (response: unknown) => void) => {
  if (message.type === "detect-fields") { const adapter = selectSiteAdapter(document, window.location); sendResponse({ site: adapter.name, fields: adapter.detectFields(document), scanned_at: new Date().toISOString() }); }
  if (message.type === "fill-fields") sendResponse(fillFields(document, message.items || []));
  return true;
});
