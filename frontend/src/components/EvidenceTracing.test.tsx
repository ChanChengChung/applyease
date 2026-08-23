import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../test/render";
import { EvidenceTracing } from "./EvidenceTracing";
import type { Material } from "../types/material";

const material: Material = {
  id: 1,
  job_id: 2,
  material_type: "resume",
  text: "Built ApplyEase",
  character_count: 15,
  fact_check_passed: true,
  warnings: [],
  generation_method: "rules",
  created_at: "2026-08-21T00:00:00Z",
  sources: [
    {
      experience_id: 9,
      experience_title: "ApplyEase",
      text: "Built a grounded application workspace.",
      claim: "Built ApplyEase",
    },
  ],
};

describe("EvidenceTracing", () => {
  it("challenges a claim without inventing new evidence", async () => {
    const user = userEvent.setup();
    renderWithProviders(<EvidenceTracing material={material} />);
    expect(screen.getByText("Built ApplyEase")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "检验这项主张" }));
    expect(screen.getByText("面试可辩护性检查")).toBeInTheDocument();
    expect(screen.getByText(/不要添加该来源无法支持/)).toBeInTheDocument();
  });
});
