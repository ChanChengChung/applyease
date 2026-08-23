import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../../test/render";

const api = vi.hoisted(() => ({
  deleteOpportunitySearch: vi.fn(),
  listOpportunitySearches: vi.fn(),
  searchOpportunities: vi.fn(),
  importOpportunityAndTrack: vi.fn(),
}));
const profileApi = vi.hoisted(() => ({ listExperiences: vi.fn() }));
vi.mock("../../services/opportunityApi", () => api);
vi.mock("../../services/profileApi", () => profileApi);

import { OpportunityRadarPage } from "./OpportunityRadarPage";

const search = {
  id: 8,
  career_goal: "quant technology internship",
  location: "Hong Kong",
  work_preference: "any" as const,
  timing: "Summer",
  language: "zh-CN" as const,
  used_fallback: false,
  created_at: "2026-08-21T00:00:00Z",
  sources: [
    { title: "Official opening", url: "https://careers.example.com/role" },
  ],
  opportunities: [
    {
      company: "Example Capital",
      title: "Quant Technology Intern",
      location: "Hong Kong",
      employment_type: "Internship",
      why_match: "Confirmed Python evidence matches the role.",
      evidence_used: ["Python project"],
      gaps_to_address: ["Probability"],
      next_step: "Read the official posting.",
      source_title: "Official opening",
      source_url: "https://careers.example.com/role",
    },
  ],
};

describe("OpportunityRadarPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listOpportunitySearches.mockResolvedValue([]);
    api.searchOpportunities.mockResolvedValue(search);
    profileApi.listExperiences.mockResolvedValue([
      {
        id: 21,
        title: "Confirmed Python Project",
        organization: "HKU",
        description: "Built a reliable Python pipeline.",
        skills: ["Python"],
        achievements: [],
        source_file: "CV.pdf",
        category: "project",
        confirmed: true,
      },
    ]);
  });

  it("requires explicit consent and then searches from the evidence brief", async () => {
    const user = userEvent.setup();
    renderWithProviders(<OpportunityRadarPage />);

    await screen.findByText("Confirmed Python Project");
    expect(screen.getByRole("button", { name: "搜索适合职位" })).toBeDisabled();
    await user.click(
      screen.getByRole("checkbox", {
        name: /我同意使用下方已确认经历预览进行公开网络搜索/,
      }),
    );
    await user.selectOptions(screen.getByLabelText("职业类别"), "quant");
    await user.click(screen.getByRole("button", { name: "搜索适合职位" }));

    await waitFor(() =>
      expect(api.searchOpportunities).toHaveBeenCalledWith(
        expect.objectContaining({
          career_goal: "寻找符合我已确认经历的 量化研究与交易 早期职业机会。",
          consent_to_web_search: true,
          experience_ids: [21],
        }),
      ),
    );
    expect(
      await screen.findByText("Quant Technology Intern"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Confirmed Python evidence matches the role."),
    ).toBeInTheDocument();
    expect(screen.getByText("Confirmed Python Project")).toBeInTheDocument();
  });

  it("lets the student switch from all evidence to a selected subset", async () => {
    const user = userEvent.setup();
    profileApi.listExperiences.mockResolvedValue([
      ...(await profileApi.listExperiences()),
      {
        id: 22,
        title: "Confirmed Research Project",
        organization: "CUHK",
        description: "Built a research prototype.",
        skills: ["Research"],
        achievements: [],
        source_file: "portfolio",
        category: "research",
        confirmed: true,
      },
    ]);
    renderWithProviders(<OpportunityRadarPage />);

    await screen.findByText("Confirmed Research Project");
    await user.click(screen.getByRole("button", { name: "选择部分经历" }));
    const experienceToggles = screen.getAllByRole("checkbox", {
      name: "使用此经历",
    });
    await user.click(experienceToggles[1]);
    await user.click(
      screen.getByRole("checkbox", {
        name: /我同意使用下方已确认经历预览进行公开网络搜索/,
      }),
    );
    await user.click(screen.getByRole("button", { name: "搜索适合职位" }));

    await waitFor(() =>
      expect(api.searchOpportunities).toHaveBeenCalledWith(
        expect.objectContaining({ experience_ids: [21] }),
      ),
    );
  });

  it("imports a reviewed role and opens its application tracker workflow", async () => {
    const user = userEvent.setup();
    const onJobImported = vi.fn();
    const onJobTracked = vi.fn();
    api.listOpportunitySearches.mockResolvedValue([search]);
    api.importOpportunityAndTrack.mockResolvedValue({
      job: {
        id: 33,
        title: "Quant Technology Intern",
        company: "Example Capital",
      },
      tracker: {
        id: 44,
        job_id: 33,
        company: "Example Capital",
        role: "Quant Technology Intern",
        status: "saved",
      },
    });
    renderWithProviders(
      <OpportunityRadarPage
        onJobImported={onJobImported}
        onJobTracked={onJobTracked}
      />,
    );

    await screen.findByText("Quant Technology Intern");
    await user.click(
      screen.getByRole("button", { name: "审核、导入并加入追踪" }),
    );
    await waitFor(() =>
      expect(api.importOpportunityAndTrack).toHaveBeenCalledWith(8, 0),
    );
    expect(onJobImported).toHaveBeenCalledWith(
      expect.objectContaining({ id: 33 }),
    );
    expect(onJobTracked).toHaveBeenCalledWith(
      expect.objectContaining({ id: 33 }),
      expect.objectContaining({ id: 44, job_id: 33 }),
    );
  });

  it("deletes a saved research history entry from the API and the page", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true),
    );
    api.listOpportunitySearches.mockResolvedValue([search]);
    api.deleteOpportunitySearch.mockResolvedValue(undefined);
    renderWithProviders(<OpportunityRadarPage />);

    await screen.findByText("Quant Technology Intern");
    await user.click(screen.getByRole("button", { name: "删除这条搜索记录" }));
    await waitFor(() =>
      expect(api.deleteOpportunitySearch).toHaveBeenCalledWith(8),
    );
    await waitFor(() =>
      expect(
        screen.queryByText("Quant Technology Intern"),
      ).not.toBeInTheDocument(),
    );
    vi.unstubAllGlobals();
  });
});
