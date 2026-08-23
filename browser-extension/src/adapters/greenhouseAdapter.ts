import type { DetectedField } from "../types";
import { detectFields, labelFor } from "../fieldDetector";
import type { SiteAdapter } from "./types";

const GREENHOUSE_HOSTS = ["greenhouse.io", "greenhouse.com"];

function hostMatches(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/^www\./, "");
  return GREENHOUSE_HOSTS.some(domain => host === domain || host.endsWith(`.${domain}`));
}

function greenhouseRoot(documentRoot: Document): Element | null {
  return documentRoot.querySelector("#grnhse_app, [data-greenhouse], .greenhouse-job-board");
}

function textFor(element: Element): string {
  const dataQa = element.getAttribute("data-qa") || element.getAttribute("data-testid") || "";
  const qaText = dataQa.replace(/[_-]+/g, " ").trim();
  const label = labelFor(element as HTMLInputElement);
  const container = element.closest(".field, [data-qa='question'], fieldset");
  const containerText = container?.querySelector("label, legend, .label")?.textContent?.trim() || "";
  return (containerText || label || qaText || element.getAttribute("name") || element.id || "").replace(/\s+/g, " ").trim();
}

function radioFields(root: Element): DetectedField[] {
  const radios = Array.from(root.querySelectorAll<HTMLInputElement>("input[type='radio']"));
  const groups = new Map<string, HTMLInputElement[]>();
  for (const radio of radios) {
    const key = radio.name || radio.closest("fieldset, .field")?.getAttribute("data-qa") || radio.id;
    if (!key) continue;
    const list = groups.get(key) || []; list.push(radio); groups.set(key, list);
  }
  return Array.from(groups.entries()).map(([key, group], index) => {
    const fieldId = `applyease-greenhouse-radio-${index}-${key.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`;
    const options = group.map(radio => {
      const escape = typeof globalThis.CSS?.escape === "function" ? globalThis.CSS.escape.bind(globalThis.CSS) : ((value: string) => value.replace(/[^a-zA-Z0-9_-]/g, "\\$&"));
      const label = radio.id ? root.querySelector(`label[for="${escape(radio.id)}"]`) : radio.closest("label");
      return (label?.textContent || radio.value || "").replace(/\s+/g, " ").trim();
    }).filter(Boolean);
    group.forEach(radio => { radio.dataset.applyeaseFieldId = fieldId; });
    const first = group[0];
    return { field_id: fieldId, label: textFor(first), name: key, html_id: "", placeholder: "", input_type: "radio", options };
  });
}

export const greenhouseAdapter: SiteAdapter = {
  name: "greenhouse",
  matches(documentRoot, location) {
    return Boolean(greenhouseRoot(documentRoot)) || hostMatches(location?.hostname || "");
  },
  detectFields(documentRoot) {
    const root = greenhouseRoot(documentRoot) || documentRoot.body || documentRoot.documentElement;
    const fields = detectFields(root).filter(field => field.input_type !== "radio");
    return [...fields, ...radioFields(root)];
  }
};
