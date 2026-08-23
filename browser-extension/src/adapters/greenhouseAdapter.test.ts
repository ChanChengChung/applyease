import { describe, expect, it } from "vitest";
import { greenhouseAdapter } from "./greenhouseAdapter";
import { selectSiteAdapter } from "./index";
import { fillFields } from "../fillController";

describe("greenhouseAdapter", () => {
  it("recognises Greenhouse markers and groups radio options", () => {
    document.body.innerHTML = `<div id="grnhse_app"><form><label for="first_name">First name</label><input id="first_name" data-qa="first_name"><fieldset class="field"><legend>Work arrangement</legend><label><input type="radio" name="work_arrangement" value="remote">Remote</label><label><input type="radio" name="work_arrangement" value="office">Office</label></fieldset><label for="cover">Cover letter</label><textarea id="cover"></textarea></form></div>`;
    expect(greenhouseAdapter.matches(document, { hostname: "example.test" } as Location)).toBe(true);
    const fields = greenhouseAdapter.detectFields(document);
    expect(fields).toHaveLength(3);
    const radio = fields.find(field => field.input_type === "radio");
    expect(radio).toMatchObject({ label: "Work arrangement", options: ["Remote", "Office"] });
  });

  it("recognises hosted Greenhouse domains and safely fills a radio answer", () => {
    document.body.innerHTML = `<form><fieldset><legend>Work arrangement</legend><label><input type="radio" name="arrangement" value="remote">Remote</label><label><input type="radio" name="arrangement" value="office">Office</label></fieldset></form>`;
    expect(greenhouseAdapter.matches(document, { hostname: "boards.greenhouse.io" } as Location)).toBe(true);
    const field = greenhouseAdapter.detectFields(document).find(item => item.input_type === "radio")!;
    const result = fillFields(document, [{ field_id: field.field_id, answer: "Office" }]);
    expect(result).toMatchObject({ filled: 1, skipped: [] });
    expect((document.querySelector("input[value=office]") as HTMLInputElement).checked).toBe(true);
  });

  it("falls back to the generic adapter on other sites", () => {
    document.body.innerHTML = `<label for="name">Name</label><input id="name">`;
    expect(selectSiteAdapter(document, { hostname: "jobs.example.com" } as Location).name).toBe("generic");
  });
});
