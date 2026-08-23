import { beforeEach, describe, expect, it } from "vitest";
import { detectFields } from "./fieldDetector";
import { fillFields } from "./fillController";

describe("fillController", () => {
  beforeEach(() => { document.body.innerHTML = `<label for="motivation">Why this role?</label><textarea id="motivation" maxlength="20"></textarea><label for="track">Track</label><select id="track"><option value="quant">Quant</option><option value="software">Software</option></select><input id="password" type="password"><input id="submit" type="submit">`; detectFields(document); });
  it("fills approved text and select fields and dispatches input/change", () => {
    const textarea = document.querySelector("textarea")!; let inputEvents = 0; let changeEvents = 0; textarea.addEventListener("input", () => inputEvents++); textarea.addEventListener("change", () => changeEvents++);
    const fields = detectFields(document); const result = fillFields(document, [{ field_id: fields[0].field_id, answer: "Interested role" }, { field_id: fields[1].field_id, answer: "Software" }]);
    expect(result.filled).toBe(2); expect(textarea.value).toBe("Interested role"); expect((document.querySelector("select") as HTMLSelectElement).value).toBe("software"); expect(inputEvents).toBe(1); expect(changeEvents).toBe(1);
  });
  it("never fills passwords, submit buttons, or over-limit values", () => {
    const fields = detectFields(document); const result = fillFields(document, [{ field_id: fields[0].field_id, answer: "This answer is too long for field" }, { field_id: fields[2].field_id, answer: "secret" }]);
    expect(result.filled).toBe(0); expect(result.skipped).toHaveLength(2); expect((document.querySelector("input[type=password]") as HTMLInputElement).value).toBe("");
  });
});
