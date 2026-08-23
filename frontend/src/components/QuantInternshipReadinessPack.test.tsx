import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../test/render";
import { QuantInternshipReadinessPack } from "./QuantInternshipReadinessPack";
import type { MatchReport } from "../types/job";

const report: MatchReport = {
  overall_score: 72,
  matched_skills: ["Python"],
  missing_skills: ["C++"],
  considered_experience_ids: [1],
  warnings: [],
  matched_required_skills: ["Python"],
  missing_required_skills: ["C++"],
  matched_preferred_skills: [],
  missing_preferred_skills: [],
  score_breakdown: {},
  job: {
    id: 1,
    title: "Quantitative Research Intern",
    company: "Polymer",
    description: "Research with Python and statistics",
    required_skills: ["Python", "C++"],
    preferred_skills: [],
    responsibilities: ["Analyse market signals and test a trading strategy."],
    qualifications: ["Collaborate closely with traders and researchers."],
    created_at: "2026-08-21T00:00:00Z",
  },
  evidence: [
    {
      requirement: "Python",
      experience_id: 1,
      experience_title: "ApplyEase",
      evidence: "Built FastAPI services with Python",
    },
  ],
};

describe("QuantInternshipReadinessPack", () => {
  it("creates role-specific rehearsal questions without repeating the evidence list", async () => {
    const user = userEvent.setup();
    renderWithProviders(<QuantInternshipReadinessPack report={report} />);
    await user.click(screen.getByRole("button", { name: "打开面试演练包" }));
    expect(
      screen.getAllByText(/Polymer · Quantitative Research Intern/).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/职位专属问题/)).toBeInTheDocument();
    expect(screen.getAllByText(/C\+\+/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Analyse market signals/)).toBeInTheDocument();
    expect(
      screen.queryByText("Built FastAPI services with Python"),
    ).not.toBeInTheDocument();
  });
});
