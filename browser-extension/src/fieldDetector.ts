export type DetectedField = { field_id: string; label: string; name: string; html_id: string; placeholder: string; input_type: string; max_characters?: number; options: string[] };

export function labelFor(element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement): string {
  if (element.id) { const escape = typeof globalThis.CSS?.escape === "function" ? globalThis.CSS.escape.bind(globalThis.CSS) : ((value: string) => value.replace(/[^a-zA-Z0-9_-]/g, "\\$&")); const linked = element.ownerDocument.querySelector(`label[for="${escape(element.id)}"]`); if (linked?.textContent) return linked.textContent.trim(); }
  const parent = element.closest("label"); if (parent?.textContent) return parent.textContent.replace(element.value || "", "").trim();
  return element.getAttribute("aria-label") || element.getAttribute("placeholder") || element.getAttribute("name") || element.id || "";
}

export function detectFields(documentRoot: ParentNode): DetectedField[] {
  const elements = Array.from(documentRoot.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>("input, textarea, select"));
  return elements.map((element, index) => {
    const type = element instanceof HTMLInputElement ? (element.type || "text").toLowerCase() : element instanceof HTMLSelectElement ? "select" : "textarea";
    const fieldId = element.dataset.applyeaseFieldId || `applyease-${index}`;
    element.dataset.applyeaseFieldId = fieldId;
    const maxLength = element instanceof HTMLSelectElement ? undefined : (element.maxLength > 0 ? element.maxLength : undefined);
    return { field_id: fieldId, label: labelFor(element), name: element.getAttribute("name") || "", html_id: element.id || "", placeholder: element.getAttribute("placeholder") || "", input_type: type, max_characters: maxLength, options: element instanceof HTMLSelectElement ? Array.from(element.options).map(option => option.text).slice(0, 100) : [] };
  }).filter(field => !["hidden", "submit", "button", "reset", "image"].includes(field.input_type));
}
