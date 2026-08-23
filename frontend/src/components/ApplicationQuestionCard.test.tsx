import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/render";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApplicationQuestionCard } from "./ApplicationQuestionCard";
import type {
  ApplicationQuestion,
  GeneratedAnswer,
} from "../types/application";

const narrative: ApplicationQuestion = {
  id: 1,
  application_id: 2,
  question: "Why this role?",
  question_type: "motivation",
  max_characters: 100,
  required: true,
  answer: { metadata: { max_words: 3, requires_user_input: false } },
  created_at: "2026-08-13",
};
const generated: GeneratedAnswer = {
  question_id: 1,
  question: "Why this role?",
  answer: "A grounded answer",
  character_count: 17,
  max_characters: 100,
  fact_check_passed: true,
  warnings: [],
  sources: [],
  status: "generated",
  generation_method: "ai",
  word_count: 3,
  max_words: 3,
};

describe("ApplicationQuestionCard", () => {
  it("never offers AI generation for sensitive manual fields", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);
    const onGenerate = vi.fn();

    const sensitive = {
      ...narrative,
      id: 2,
      question: "Visa status",
      question_type: "eligibility",
      answer: { metadata: { sensitive: true, requires_user_input: true } },
    };
    renderWithProviders(
      <ApplicationQuestionCard
        question={sensitive}
        busy={false}
        onGenerate={onGenerate}
        onSave={onSave}
      />,
    );

    expect(screen.getByText(/AI 不会推测/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "生成答案" }),
    ).not.toBeInTheDocument();

    await user.type(
      screen.getByLabelText("答案：Visa status"),
      "User supplied",
    );
    await user.click(screen.getByRole("button", { name: "保存答案" }));

    expect(onSave).toHaveBeenCalledWith("User supplied");
    expect(onGenerate).not.toHaveBeenCalled();
  });

  it("supports regeneration and blocks answers over the word limit", async () => {
    const user = userEvent.setup();
    const onGenerate = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <ApplicationQuestionCard
        question={narrative}
        answer={generated}
        busy={false}
        onGenerate={onGenerate}
        onSave={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "重新生成" }));
    expect(onGenerate).toHaveBeenCalled();

    await user.clear(screen.getByLabelText("答案：Why this role?"));
    await user.type(
      screen.getByLabelText("答案：Why this role?"),
      "one two three four",
    );

    expect(screen.getByRole("button", { name: "保存答案" })).toBeDisabled();
  });

  it("allows an answer template to be selected before generation", async () => {
    const user = userEvent.setup();
    const onTemplateChange = vi.fn();
    renderWithProviders(
      <ApplicationQuestionCard
        question={narrative}
        busy={false}
        template="auto"
        onTemplateChange={onTemplateChange}
        onGenerate={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    await user.selectOptions(
      screen.getByLabelText("回答模板：Why this role?"),
      "star",
    );

    expect(onTemplateChange).toHaveBeenCalledWith("star");
  });
});
