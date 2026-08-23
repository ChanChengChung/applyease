import { describe, expect, it } from "vitest";
import { fillFields } from "../fillController";
import { selectSiteAdapter } from "./index";
import { leverAdapter } from "./leverAdapter";

function leverForm(): string {
  return `<form class="application-form">
    <div class="application-field"><label for="name">Full name *</label><input id="name" name="name" required></div>
    <div class="application-field"><label for="email">Email *</label><input id="email" name="email" type="email" required></div>
    <div class="application-question"><label>Preferred office *</label><select name="office"><option value="">Select</option><option value="hk">Hong Kong</option></select></div>
    <fieldset class="application-question"><legend>Available this summer? *</legend><label><input type="radio" name="available" value="yes">Yes</label><label><input type="radio" name="available" value="no">No</label></fieldset>
    <div class="application-field"><label for="resume">Resume</label><input id="resume" type="file" name="resume"></div>
    <label><input type="checkbox" name="consent">I agree to data processing</label>
    <button type="submit">Submit application</button>
  </form>`;
}

describe("leverAdapter", () => {
  it("recognises global and EU hosted Lever domains", () => {
    document.body.innerHTML = "";
    expect(leverAdapter.matches(document, { hostname: "jobs.lever.co" } as Location)).toBe(true);
    expect(leverAdapter.matches(document, { hostname: "jobs.eu.lever.co" } as Location)).toBe(true);
    expect(leverAdapter.matches(document, { hostname: "lever.example.com" } as Location)).toBe(false);
  });

  it("extracts hosted fields, select options, and one radio group", () => {
    document.body.innerHTML = leverForm();
    const fields = leverAdapter.detectFields(document);
    expect(fields).toHaveLength(6);
    expect(fields.find(field => field.name === "name")).toMatchObject({ label: "Full name *", input_type: "text" });
    expect(fields.find(field => field.name === "office")?.options).toEqual(["Select", "Hong Kong"]);
    expect(fields.find(field => field.input_type === "radio")).toMatchObject({ label: "Available this summer?", options: ["Yes", "No"] });
    expect(fields.some(field => field.input_type === "file")).toBe(true);
    expect(fields.some(field => field.input_type === "submit")).toBe(false);
  });

  it("re-scans fields added after the first dynamic render", () => {
    document.body.innerHTML = `<form class="application-form"><label for="name">Name</label><input id="name"></form>`;
    expect(leverAdapter.detectFields(document)).toHaveLength(1);
    document.querySelector("form")!.insertAdjacentHTML("beforeend", `<div class="application-question"><label for="why">Why us?</label><textarea id="why"></textarea></div>`);
    expect(leverAdapter.detectFields(document)).toHaveLength(2);
  });

  it("fills approved Lever fields while leaving file and consent controls untouched", () => {
    document.body.innerHTML = leverForm();
    const fields = leverAdapter.detectFields(document);
    const name = fields.find(field => field.name === "name")!;
    const radio = fields.find(field => field.input_type === "radio")!;
    const file = fields.find(field => field.input_type === "file")!;
    const consent = fields.find(field => field.input_type === "checkbox")!;
    const result = fillFields(document, [
      { field_id: name.field_id, answer: "Chen Zhengzhong" },
      { field_id: radio.field_id, answer: "Yes" },
      { field_id: file.field_id, answer: "/tmp/cv.pdf" },
      { field_id: consent.field_id, answer: "true" }
    ]);
    expect(result.filled).toBe(2);
    expect(result.skipped).toEqual(expect.arrayContaining([file.field_id, consent.field_id]));
    expect((document.querySelector("#name") as HTMLInputElement).value).toBe("Chen Zhengzhong");
    expect((document.querySelector("input[value=yes]") as HTMLInputElement).checked).toBe(true);
    expect((document.querySelector("input[type=checkbox]") as HTMLInputElement).checked).toBe(false);
  });

  it("selects Lever ahead of the generic adapter when its form marker exists", () => {
    document.body.innerHTML = leverForm();
    expect(selectSiteAdapter(document, { hostname: "careers.example.com" } as Location).name).toBe("lever");
  });
});
