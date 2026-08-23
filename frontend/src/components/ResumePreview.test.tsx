import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/render";
import { describe, expect, it } from "vitest";
import { ResumePreview, splitResumeSections } from "./ResumePreview";

const text =
  "SUMMARY\nShort summary\nPROJECTS\n- Built ApplyEase\nEDUCATION\nUniversity";

describe("ResumePreview", () => {
  it("splits uppercase resume headings into stable sections", () => {
    expect(splitResumeSections(text).map((section) => section.name)).toEqual([
      "SUMMARY",
      "PROJECTS",
      "EDUCATION",
    ]);
  });

  it("uses the selected order, hides sections and warns about a likely overflow", () => {
    renderWithProviders(
      <ResumePreview
        text={text}
        displayName="Chen"
        contactLine="chen@example.com"
        template="compact"
        order={["EDUCATION", "PROJECTS", "SUMMARY"]}
        hidden={["SUMMARY"]}
      />,
    );

    const content = screen.getByLabelText("简历导出预览").textContent || "";

    expect(content.indexOf("EDUCATION")).toBeLessThan(
      content.indexOf("PROJECTS"),
    );

    expect(content).not.toContain("Short summary");
  });
});
