import { beforeEach, describe, expect, it } from "vitest";
import { detectFields } from "./fieldDetector";

describe("fieldDetector", () => {
  beforeEach(() => { document.body.innerHTML = `<form><label for="motivation">Why this role?</label><textarea id="motivation" maxlength="300"></textarea><label for="track">Track</label><select id="track"><option>Quant</option><option>Software</option></select><input type="hidden" id="csrf"><input type="password" id="password"></form>`; });
  it("extracts labels, limits, options, and excludes hidden fields", () => {
    const fields = detectFields(document);
    expect(fields).toHaveLength(3);
    expect(fields[0]).toMatchObject({ label: "Why this role?", input_type: "textarea", max_characters: 300 });
    expect(fields[1]).toMatchObject({ label: "Track", input_type: "select", options: ["Quant", "Software"] });
  });
});
