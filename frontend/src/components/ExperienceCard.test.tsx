import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/render";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ExperienceCard } from "./ExperienceCard";
import type { Experience } from "../types/experience";

const item: Experience = {
  id: 62,
  title: "AI Developer",
  organization: "Novelflow",
  description: "Built an AI writing platform.",
  skills: ["React", "FastAPI"],
  achievements: [
    { text: "Built 10 components", source: "CV.pdf", verified: false },
  ],
  source_file: "CV.pdf",
  category: "project",
  confirmed: false,
};

describe("ExperienceCard", () => {
  it("edits all user-reviewable fields and saves normalized skills", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <ExperienceCard item={item} onSave={onSave} onDelete={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "编辑" }));

    await user.clear(screen.getByLabelText("标题"));
    await user.type(screen.getByLabelText("标题"), "Co-founder");

    await user.clear(screen.getByLabelText("技能（用逗号分隔）"));
    await user.type(
      screen.getByLabelText("技能（用逗号分隔）"),
      "Python, FastAPI",
    );

    await user.clear(screen.getByLabelText("成果 1"));
    await user.type(screen.getByLabelText("成果 1"), "Secured seed funding");

    await user.click(screen.getByRole("button", { name: "保存修改" }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Co-founder",
        skills: ["Python", "FastAPI"],
        achievements: [
          expect.objectContaining({
            text: "Secured seed funding",
            source: "CV.pdf",
          }),
        ],
      }),
    );

    expect(
      screen.queryByRole("button", { name: "保存修改" }),
    ).not.toBeInTheDocument();
  });

  it("prevents saving an empty title", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();

    renderWithProviders(
      <ExperienceCard item={item} onSave={onSave} onDelete={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "编辑" }));
    await user.clear(screen.getByLabelText("标题"));

    expect(screen.getByRole("button", { name: "保存修改" })).toBeDisabled();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("lets the user correct the AI-selected evidence category", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(
      <ExperienceCard item={item} onSave={onSave} onDelete={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "编辑" }));
    await user.selectOptions(screen.getByLabelText("经历类别"), "research");
    await user.click(screen.getByRole("button", { name: "保存修改" }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ category: "research" }),
    );
  });

  it("moves an experience to a different folder without opening the full editor", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(
      <ExperienceCard item={item} onSave={onSave} onDelete={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "调整文件夹" }));
    await user.selectOptions(screen.getByLabelText("经历类别"), "research");
    await user.click(screen.getByRole("button", { name: "移动经历" }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ id: item.id, category: "research" }),
    );
  });

  it("cancels edits and restores the persisted item", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <ExperienceCard item={item} onSave={vi.fn()} onDelete={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "编辑" }));
    await user.clear(screen.getByLabelText("标题"));
    await user.type(screen.getByLabelText("标题"), "Wrong title");

    await user.click(screen.getByRole("button", { name: "取消" }));
    await user.click(screen.getByRole("button", { name: "编辑" }));

    expect(screen.getByLabelText("标题")).toHaveValue("AI Developer");
  });

  it("confirms an experience and displays save failures", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockRejectedValue(new Error("后端暂时不可用"));

    renderWithProviders(
      <ExperienceCard item={item} onSave={onSave} onDelete={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "确认并解锁证据" }));

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ confirmed: true }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "后端暂时不可用",
    );
  });

  it("delegates deletion to the page", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <ExperienceCard item={item} onSave={vi.fn()} onDelete={onDelete} />,
    );

    await user.click(screen.getByRole("button", { name: "删除" }));
    expect(onDelete).toHaveBeenCalledWith(item);
  });

  it("renders extracted personal details as clear labelled fields", () => {
    const personal: Experience = {
      ...item,
      title: "Chen Zhengzhong",
      organization: "Personal profile",
      category: "personal",
      description:
        "Name: Chen Zhengzhong\nEmail: chen@example.com\nPhone: +852 1234 5678",
    };

    renderWithProviders(
      <ExperienceCard item={personal} onSave={vi.fn()} onDelete={vi.fn()} />,
    );

    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("chen@example.com")).toBeInTheDocument();
    expect(screen.getByText("+852 1234 5678")).toBeInTheDocument();
  });
});
