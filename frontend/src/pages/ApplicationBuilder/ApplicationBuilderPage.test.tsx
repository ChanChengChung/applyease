import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  generateResume: vi.fn(),
  generateCoverLetter: vi.fn(),
  generateAnswer: vi.fn(),
  listMaterials: vi.fn(),
  updateMaterial: vi.fn(),
  downloadResume: vi.fn(),
  saveDownload: vi.fn(),
}));
vi.mock("../../services/materialApi", () => api);
import { ApplicationBuilderPage } from "./ApplicationBuilderPage";

const material = {
  id: 4,
  job_id: 3,
  material_type: "resume",
  text: "Generated resume",
  character_count: 16,
  fact_check_passed: true,
  warnings: [],
  sources: [],
  generation_method: "ai",
  created_at: "2026-08-13T00:00:00Z",
};

describe("ApplicationBuilderPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.generateResume.mockResolvedValue(material);
    api.listMaterials.mockResolvedValue([material]);
    api.updateMaterial.mockResolvedValue({
      ...material,
      text: "Edited",
      generation_method: "user_edited",
    });
    api.downloadResume.mockResolvedValue({
      blob: new Blob(["file"]),
      filename: "resume.pdf",
    });
  });

  it("generates a resume and loads version history", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ApplicationBuilderPage initialJobId={3} />);

    await user.click(screen.getByRole("button", { name: "生成定制简历" }));

    expect(api.generateResume).toHaveBeenCalledWith(3, "zh-CN");
    expect(
      await screen.findByDisplayValue("Generated resume"),
    ).toBeInTheDocument();
    expect(screen.getByText("申请材料可信度检查")).toBeInTheDocument();
    expect(screen.getByLabelText("可信度评分 55/100")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("生成语言"), "zh-CN");
    await user.click(screen.getByRole("button", { name: "生成定制简历" }));
    expect(api.generateResume).toHaveBeenLastCalledWith(3, "zh-CN");

    expect(api.listMaterials).toHaveBeenCalledWith(3);
    expect(screen.getByText("历史版本")).toBeInTheDocument();
  });

  it("opens the newest saved material when history is loaded", async () => {
    const user = userEvent.setup();
    const newest = {
      ...material,
      id: 9,
      text: "Newest saved resume",
      created_at: "2026-08-20T00:00:00Z",
    };
    api.listMaterials.mockResolvedValue([newest, material]);
    renderWithProviders(<ApplicationBuilderPage initialJobId={3} />);

    await user.click(screen.getByRole("button", { name: "加载历史版本" }));

    expect(await screen.findByDisplayValue("Newest saved resume")).toBeInTheDocument();
    expect(screen.getByText("已保存 2 个版本")).toBeInTheDocument();
  });

  it("requires selecting a target before generating", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ApplicationBuilderPage />);
    await user.click(screen.getByRole("button", { name: "生成定制简历" }));

    expect(screen.getByRole("button", { name: "生成定制简历" })).toBeDisabled();
    expect(api.generateResume).not.toHaveBeenCalled();
  });

  it("passes tone and the applicant's requested emphasis into answer generation", async () => {
    const user = userEvent.setup();
    api.generateAnswer.mockResolvedValue({
      ...material,
      material_type: "application_answer",
      text: "A grounded answer",
    });
    renderWithProviders(<ApplicationBuilderPage initialJobId={3} />);

    await user.type(
      screen.getByLabelText("申请题目"),
      "Why are you interested in this role?",
    );
    await user.selectOptions(screen.getByLabelText("回答语气"), "technical");
    await user.type(
      screen.getByLabelText("希望重点包含什么？"),
      "research mindset",
    );
    await user.click(screen.getByRole("button", { name: "生成申请题答案" }));

    expect(api.generateAnswer).toHaveBeenCalledWith(
      3,
      "Why are you interested in this role?",
      300,
      "zh-CN",
      { tone: "technical", desiredContent: "research mindset" },
    );
  });

  it("exports the selected resume template and optional evidence appendix", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ApplicationBuilderPage initialJobId={3} />);

    await user.click(screen.getByRole("button", { name: "生成定制简历" }));

    await user.type(
      screen.getByLabelText("姓名（导出必填）"),
      "Chen Zhengzhong",
    );

    await user.type(screen.getByLabelText("电子邮件"), "chen@example.com");

    await user.selectOptions(screen.getByLabelText("简历模板"), "compact");

    await user.click(screen.getByLabelText("附加来源附录（仅供审核）"));

    await user.click(screen.getByRole("button", { name: "下载 PDF" }));

    expect(api.downloadResume).toHaveBeenCalledWith(
      4,
      "pdf",
      "compact",
      true,
      "Chen Zhengzhong",
      "",
      expect.objectContaining({
        email: "chen@example.com",
        phone: "",
        location: "",
      }),
      expect.any(Array),
      expect.any(Array),
      { fontStyle: "default", density: "standard", accent: "template" },
    );

    expect(api.saveDownload).toHaveBeenCalledWith(
      expect.objectContaining({ filename: "resume.pdf" }),
    );
  });

  it("updates the resume preview as the user edits, before saving", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ApplicationBuilderPage initialJobId={3} />);

    await user.click(screen.getByRole("button", { name: "生成定制简历" }));
    const editor = await screen.findByLabelText("材料内容");
    await user.clear(editor);
    await user.type(editor, "Live preview evidence");

    expect(screen.getByLabelText("简历导出预览")).toHaveTextContent(
      "Live preview evidence",
    );
    expect(api.updateMaterial).not.toHaveBeenCalled();
  });

  it("blocks export controls when the selected version fails fact checking", async () => {
    api.generateResume.mockResolvedValueOnce({
      ...material,
      fact_check_passed: false,
      warnings: ["unsupported claim"],
    });

    api.listMaterials.mockResolvedValueOnce([
      { ...material, fact_check_passed: false },
    ]);

    const user = userEvent.setup();
    renderWithProviders(<ApplicationBuilderPage initialJobId={3} />);

    await user.click(screen.getByRole("button", { name: "生成定制简历" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "请先修正事实检查警告",
    );

    expect(screen.getByRole("button", { name: "下载 DOCX" })).toBeDisabled();

    expect(screen.getByRole("button", { name: "下载 PDF" })).toBeDisabled();
  });
});
