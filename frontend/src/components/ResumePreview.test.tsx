import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/render";
import { describe, expect, it } from "vitest";
import { normalizeResumeLine, ResumePreview, splitResumeSections } from "./ResumePreview";

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

  it("normalizes legacy localized labels in the English export preview", () => {
    expect(normalizeResumeLine("技能: MATLAB")).toBe("Skills: MATLAB");
    expect(normalizeResumeLine("目标职位: Software Engineer")).toBe(
      "Target Role: Software Engineer",
    );
    expect(normalizeResumeLine("相关经历")).toBe("SELECTED EXPERIENCE");
    expect(normalizeResumeLine("技能: MATLAB", "zh-CN")).toBe("技能: MATLAB");
  });
});
