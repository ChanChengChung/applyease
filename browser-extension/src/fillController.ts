export type FillResult = { filled: number; skipped: string[] };

const NEVER_FILL = new Set(["password", "file", "hidden", "checkbox", "submit", "button", "reset", "image"]);

function setNativeValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = Object.getPrototypeOf(element) as { value?: PropertyDescriptor };
  const descriptor = Object.getOwnPropertyDescriptor(prototype, "value") || Object.getOwnPropertyDescriptor(Object.getPrototypeOf(prototype), "value");
  if (descriptor?.set) descriptor.set.call(element, value); else element.value = value;
}

export function fillFields(documentRoot: Document, items: Array<{ field_id: string; answer: string }>): FillResult {
  const byId = new Map(items.map(item => [item.field_id, item.answer])); const skipped: string[] = []; let filled = 0; const handledRadioGroups = new Set<string>();
  for (const element of Array.from(documentRoot.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>("input, textarea, select"))) {
    const fieldId = element.dataset.applyeaseFieldId; const answer = fieldId ? byId.get(fieldId) : undefined;
    if (answer === undefined) continue;
    const type = element instanceof HTMLInputElement ? element.type.toLowerCase() : element instanceof HTMLSelectElement ? "select" : "textarea";
    if (type === "radio") {
      if (handledRadioGroups.has(fieldId!)) continue;
      handledRadioGroups.add(fieldId!);
      const group = Array.from(documentRoot.querySelectorAll<HTMLInputElement>(`input[type="radio"][data-applyease-field-id="${fieldId}"]`));
      const normalized = answer.trim().toLowerCase();
      const target = group.find(candidate => {
        const escape = typeof globalThis.CSS?.escape === "function" ? globalThis.CSS.escape.bind(globalThis.CSS) : ((value: string) => value.replace(/[^a-zA-Z0-9_-]/g, "\\$&"));
        const label = candidate.id ? documentRoot.querySelector(`label[for="${escape(candidate.id)}"]`) : candidate.closest("label");
        return (label?.textContent || candidate.value).trim().toLowerCase() === normalized || candidate.value.toLowerCase() === normalized;
      });
      if (!target) { skipped.push(fieldId!); continue; }
      target.checked = true; target.dispatchEvent(new Event("input", { bubbles: true })); target.dispatchEvent(new Event("change", { bubbles: true })); filled++; continue;
    }
    if (NEVER_FILL.has(type)) { skipped.push(fieldId!); continue; }
    if (element instanceof HTMLSelectElement) {
      const normalized = answer.trim().toLowerCase(); const option = Array.from(element.options).find(candidate => candidate.text.trim().toLowerCase() === normalized || candidate.value === answer);
      if (!option) { skipped.push(fieldId!); continue; }
      element.value = option.value;
    } else {
      if (element.maxLength > 0 && answer.length > element.maxLength) { skipped.push(fieldId!); continue; }
      setNativeValue(element, answer);
    }
    element.dispatchEvent(new Event("input", { bubbles: true })); element.dispatchEvent(new Event("change", { bubbles: true })); filled++;
  }
  return { filled, skipped };
}
