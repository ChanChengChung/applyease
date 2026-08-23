import { beforeEach, describe, expect, it, vi } from "vitest";
import { downloadResume, saveDownload } from "./materialApi";

describe("resume export API", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("downloads a named template artifact", async () => {
    const fetchMock = vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(new Blob(["pdf"]), {
        status: 200,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition":
            'attachment; filename="ApplyEase-role-modern.pdf"',
        },
      }),
    );

    const result = await downloadResume(
      7,
      "pdf",
      "modern",
      true,
      "Chen Zhengzhong",
      "chen@example.com",
      ["PROJECTS"],
      ["EDUCATION"],
    );

    expect(result.filename).toBe("ApplyEase-role-modern.pdf");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/materials\/7\/export$/),
      expect.objectContaining({ method: "POST" }),
    );

    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual(
      expect.objectContaining({
        format: "pdf",
        template: "modern",
        include_sources: true,
        display_name: "Chen Zhengzhong",
        section_order: ["PROJECTS"],
        hidden_sections: ["EDUCATION"],
      }),
    );
  });

  it("surfaces backend fact-check export errors", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Resolve fact-check warnings" }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      downloadResume(7, "docx", "classic", false, "Test User", ""),
    ).rejects.toThrow("Resolve fact-check warnings");
  });

  it("creates and revokes a browser download URL", () => {
    const create = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:test");
    const revoke = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => {});

    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});

    saveDownload({ blob: new Blob(["file"]), filename: "resume.docx" });

    expect(create).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();
    expect(revoke).toHaveBeenCalledWith("blob:test");
  });
});
