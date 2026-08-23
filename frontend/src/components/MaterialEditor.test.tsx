import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/render";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MaterialEditor } from "./MaterialEditor";
import type { Material } from "../types/material";

const material: Material = {
  id: 1,
  job_id: 2,
  material_type: "resume",
  text: "Original text",
  character_count: 13,
  fact_check_passed: true,
  warnings: [],
  sources: [
    { experience_id: 7, experience_title: "Project", text: "Source quote" },
  ],
  generation_method: "ai",
  created_at: "2026-08-13T00:00:00Z",
};

describe("MaterialEditor", () => {
  it("edits and saves material text", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(<MaterialEditor material={material} onSave={onSave} />);

    const editor = screen.getByLabelText("材料内容");
    await user.clear(editor);
    await user.type(editor, "Revised text");

    await user.click(screen.getByRole("button", { name: "保存修改" }));

    expect(onSave).toHaveBeenCalledWith("Revised text");
  });

  it("shows fact warnings and save errors", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockRejectedValue(new Error("保存失败"));

    renderWithProviders(
      <MaterialEditor
        material={{
          ...material,
          fact_check_passed: false,
          warnings: ["数字未经验证"],
        }}
        onSave={onSave}
      />,
    );

    expect(screen.getByText("数字未经验证")).toBeInTheDocument();
    expect(screen.queryByText(/Source quote/)).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("材料内容"), " changed");
    await user.click(screen.getByRole("button", { name: "保存修改" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("保存失败");
  });

  it("blocks edits beyond an application answer limit", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <MaterialEditor
        material={{ ...material, max_characters: 10, text: "short" }}
        onSave={vi.fn()}
      />,
    );

    await user.type(screen.getByLabelText("材料内容"), "12345678901");

    expect(screen.getByText("超过申请题目的字符限制。")).toBeInTheDocument();

    expect(screen.getByRole("button", { name: "保存修改" })).toBeDisabled();
  });
});
