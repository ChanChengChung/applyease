import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  detectQuestions: vi.fn(),
  detectScreenshot: vi.fn(),
  getLatestApplication: vi.fn(),
  getSavedAnswers: vi.fn(),
  getBatchGenerationTask: vi.fn(),
  generateQuestionAnswer: vi.fn(),
  generateAllAnswers: vi.fn(),
  updateQuestionAnswer: vi.fn(),
}));
vi.mock("../../services/applicationApi", () => api);
import { ApplicationFormPage } from "./ApplicationFormPage";

const questions = [
  {
    id: 1,
    application_id: 8,
    question: "Visa status",
    question_type: "eligibility",
    max_characters: 300,
    required: true,
    answer: { metadata: { sensitive: true, requires_user_input: true } },
    created_at: "2026",
  },
  {
    id: 2,
    application_id: 8,
    question: "Why this role?",
    question_type: "motivation",
    max_characters: 300,
    required: true,
    answer: { metadata: { requires_user_input: false } },
    created_at: "2026",
  },
];
const application = {
  id: 8,
  job_id: 3,
  raw_text: "Visa status\nWhy this role?",
  questions,
  created_at: "2026",
};
const results = [
  {
    question_id: 1,
    question: "Visa status",
    answer: "",
    character_count: 0,
    max_characters: 300,
    fact_check_passed: false,
    warnings: ["manual"],
    sources: [],
    status: "manual_required",
    generation_method: "none",
    word_count: 0,
  },
  {
    question_id: 2,
    question: "Why this role?",
    answer: "Grounded answer",
    character_count: 15,
    max_characters: 300,
    fact_check_passed: true,
    warnings: [],
    sources: [],
    status: "generated",
    generation_method: "ai",
    word_count: 2,
  },
];

describe("ApplicationFormPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.detectQuestions.mockResolvedValue(application);
    api.detectScreenshot.mockResolvedValue(application);
    api.getLatestApplication.mockRejectedValue(
      new Error("No saved application"),
    );
    api.getSavedAnswers.mockResolvedValue([]);
    api.generateAllAnswers.mockResolvedValue({
      task_id: "task-1",
      status: "completed",
      completed: 2,
      total: 2,
      results,
      errors: [],
    });
  });

  it("detects fields and batch-generates only answerable results", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ApplicationFormPage initialJobId={3} />);

    await user.type(
      screen.getByLabelText("申请页面文字"),
      "Visa status\nWhy this role?",
    );

    await user.click(screen.getByRole("button", { name: "识别申请字段" }));

    expect(await screen.findByText("识别到 2 个字段")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "生成所有可回答问题" }),
    );

    expect(api.generateAllAnswers).toHaveBeenCalledWith(8, false, "auto", "zh-CN");
    expect(
      await screen.findByDisplayValue("Grounded answer"),
    ).toBeInTheDocument();

    expect(screen.getByText(/AI 不会推测/)).toBeInTheDocument();
  });

  it("reports detection errors and restores controls", async () => {
    const user = userEvent.setup();
    api.detectQuestions.mockRejectedValue(new Error("没有识别到字段"));
    renderWithProviders(<ApplicationFormPage initialJobId={3} />);

    await user.type(
      screen.getByLabelText("申请页面文字"),
      "long enough form text",
    );

    await user.click(screen.getByRole("button", { name: "识别申请字段" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "没有识别到字段",
    );
    expect(screen.getByRole("button", { name: "识别申请字段" })).toBeEnabled();
  });

  it("requires explicit cloud OCR consent before uploading a screenshot", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ApplicationFormPage initialJobId={3} />);

    const file = new File(["png"], "form.png", { type: "image/png" });

    await user.upload(screen.getByLabelText("上传申请表截图"), file);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "必须同意发送到 Gemini",
    );

    expect(api.detectScreenshot).not.toHaveBeenCalled();

    await user.click(screen.getByRole("checkbox"));
    await user.upload(screen.getByLabelText("上传申请表截图"), file);

    await waitFor(() =>
      expect(api.detectScreenshot).toHaveBeenCalledWith(3, file, true),
    );
  });

  it("sends the chosen batch template to generation", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ApplicationFormPage initialJobId={3} />);
    await user.type(
      screen.getByLabelText("申请页面文字"),
      "Visa status\nWhy this role?",
    );
    await user.click(screen.getByRole("button", { name: "识别申请字段" }));
    await user.selectOptions(screen.getByLabelText("批量回答模板"), "star");
    await user.click(
      screen.getByRole("button", { name: "生成所有可回答问题" }),
    );
    expect(api.generateAllAnswers).toHaveBeenCalledWith(8, false, "star", "zh-CN");
  });

  it("detects the built-in demo questions without waiting for state to settle", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ApplicationFormPage initialJobId={3} />);

    await user.click(screen.getByRole("button", { name: "载入演示问题" }));

    await waitFor(() =>
      expect(api.detectQuestions).toHaveBeenCalledWith(
        3,
        expect.stringContaining("Full name *"),
      ),
    );
  });
});
