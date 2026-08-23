import type { DetectedField } from "../types";
import { detectFields, labelFor } from "../fieldDetector";
import type { SiteAdapter } from "./types";

function leverHost(hostname: string): boolean {
  const host = hostname.toLowerCase().replace(/^www\./, "");
  return host === "jobs.lever.co" || host === "jobs.eu.lever.co";
}

function leverRoot(documentRoot: Document): Element | null {
  return documentRoot.querySelector("form.application-form, .application-form, [data-qa='application-form'], form[action*='lever.co']");
}

function cleanText(value: string): string {
  return value.replace(/\s+/g, " ").replace(/\s*\*\s*$/, "").replace(/\s*required\s*$/i, "").trim();
}

function questionLabel(element: HTMLInputElement): string {
  const container = element.closest(".application-question, .application-field, .application-additional, fieldset, [data-qa='question']");
  const explicit = container?.querySelector(":scope > label, :scope > legend, :scope > .application-label, :scope > [data-qa='label']")?.textContent || "";
  const dataLabel = element.getAttribute("data-qa")?.replace(/[_-]+/g, " ") || "";
  return cleanText(explicit || labelFor(element) || dataLabel || element.name || element.id);
}

function radioFields(root: Element): DetectedField[] {
  const groups = new Map<string, HTMLInputElement[]>();
  for (const radio of Array.from(root.querySelectorAll<HTMLInputElement>("input[type='radio']"))) {
    const key = radio.name || radio.closest("fieldset, .application-question")?.getAttribute("data-qa") || radio.id;
    if (!key || radio.disabled) continue;
    groups.set(key, [...(groups.get(key) || []), radio]);
  }
  return Array.from(groups.entries()).map(([name, radios], index) => {
    const fieldId = `applyease-lever-radio-${index}-${name.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`;
    radios.forEach(radio => { radio.dataset.applyeaseFieldId = fieldId; });
    const options = radios.map(radio => cleanText(radio.closest("label")?.textContent || (radio.id ? labelFor(radio) : "") || radio.value)).filter(Boolean);
    return { field_id: fieldId, label: questionLabel(radios[0]), name, html_id: "", placeholder: "", input_type: "radio", options };
  });
}

export const leverAdapter: SiteAdapter = {
  name: "lever",
  matches(documentRoot, location) { return leverHost(location?.hostname || "") || Boolean(leverRoot(documentRoot)); },
  detectFields(documentRoot) {
    const root = leverRoot(documentRoot) || documentRoot.body || documentRoot.documentElement;
    const regular = detectFields(root).filter(field => field.input_type !== "radio");
    return [...regular, ...radioFields(root)];
  }
};
