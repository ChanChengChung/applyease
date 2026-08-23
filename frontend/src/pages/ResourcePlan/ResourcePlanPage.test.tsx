import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getRecommendations: vi.fn(),
  getStarterPlan: vi.fn(),
  getSavedStarterPlan: vi.fn(),
  updateStarterPlan: vi.fn(),
  refineStarterPlan: vi.fn(),
  getResearchPlan: vi.fn(),
  getSavedResearchPlan: vi.fn(),
  updateResearchPlan: vi.fn(),
  deleteResearchPlan: vi.fn(),
  completeResource: vi.fn(),
  createExperienceDraft: vi.fn(),
  checkResourceHealth: vi.fn(),
  submitResourceFeedback: vi.fn(),
}));
vi.mock("../../services/resourceApi", () => api);
const jobsApi = vi.hoisted(() => ({ listJobs: vi.fn() }));
vi.mock("../../services/jobApi", () => jobsApi);
import { ResourcePlanPage } from "./ResourcePlanPage";
import { StarterPlanner } from "../../components/StarterPlanner";

const resource = {
  id: 4,
  title: "Docker Get Started",
  url: "https://docs.docker.com/get-started/",
  provider: "Docker",
  skills: ["Docker"],
  difficulty: "beginner",
  duration_hours: 4,
  free: true,
  description: "Official guide",
  project: {
    title: "Containerized service",
    task: "Containerize an API",
    estimated_days: 5,
    deliverables: ["Dockerfile"],
    completion_criteria: ["Health check passes"],
    cv_bullet_template: "Containerized an API.",
  },
  verified: true,
  completed: false,
  match_score: 92,
  matched_skills: ["Docker"],
  recommendation_reason: "覆盖技能：Docker；4 小时，适合 beginner 水平。",
  created_at: "2026",
};

describe("ResourcePlanPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    jobsApi.listJobs.mockResolvedValue([
      {
        id: 3,
        title: "AI Intern",
        company: "Polymer",
        description:
          "Build useful systems for applied artificial intelligence.",
        required_skills: ["Docker"],
        preferred_skills: [],
        responsibilities: [],
        qualifications: [],
        created_at: "2026",
      },
    ]);
    api.getRecommendations.mockResolvedValue([resource]);
    api.getStarterPlan.mockResolvedValue({
      id: 4,
      interest: "AI and finance",
      focus: "quant",
      headline: "Start with a real research habit.",
      first_action: "Write a hypothesis before coding.",
      milestones: ["Explore one official resource"],
      resources: [resource],
      used_fallback: false,
      created_at: "2026",
      updated_at: "2026",
    });
    api.getResearchPlan.mockResolvedValue({
      id: 12,
      job_id: 3,
      profile_summary: "Research brief",
      gaps: ["Evaluation design"],
      method: ["Compare baselines"],
      sources: [{ title: "Official resource", url: "https://example.com" }],
      searched_at: "2026-08-21T00:00:00Z",
      created_at: "2026",
      updated_at: "2026",
      used_fallback: false,
    });
    api.getSavedResearchPlan.mockRejectedValue(new Error("No saved plan"));
    api.getSavedStarterPlan.mockRejectedValue(
      new Error("No saved starter plan"),
    );
    api.updateStarterPlan.mockImplementation((_id: number, value: object) =>
      Promise.resolve({
        id: 4,
        ...value,
        resources: [resource],
        used_fallback: false,
        created_at: "2026",
        updated_at: "2026",
      }),
    );
    api.updateResearchPlan.mockImplementation((_id: number, value: object) =>
      Promise.resolve({
        id: 12,
        job_id: 3,
        ...value,
        searched_at: "2026",
        created_at: "2026",
        updated_at: "2026",
        used_fallback: false,
      }),
    );
    api.deleteResearchPlan.mockResolvedValue(undefined);
    api.completeResource.mockResolvedValue({ ...resource, completed: true });
    api.createExperienceDraft.mockResolvedValue({
      id: 9,
      title: "Containerized service",
    });
    api.checkResourceHealth.mockResolvedValue({
      ...resource,
      link_status: "healthy",
      last_checked_at: "2026-08-19T00:00:00Z",
    });
    api.submitResourceFeedback.mockResolvedValue({
      id: 8,
      message: "Feedback recorded",
    });
  });

  it("loads explainable recommendations using user filters", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ResourcePlanPage />);

    await screen.findByRole("button", { name: /我要申请的职位/ });
    await user.click(screen.getByRole("button", { name: /我要申请的职位/ }));
    await user.selectOptions(screen.getByLabelText("选择已分析职位"), "3");
    await user.click(screen.getByRole("button", { name: "完成作品集项目" }));
    await user.selectOptions(screen.getByLabelText("你的水平"), "beginner");
    await user.click(screen.getByLabelText("只看免费资源"));
    await user.click(screen.getByRole("button", { name: "生成学习计划" }));

    await waitFor(() =>
      expect(api.getRecommendations).toHaveBeenCalledWith(3, {
        level: "beginner",
        max_total_hours: 6,
        free_only: true,
        limit: 12,
        goal: "project",
        language: "zh-CN",
      }),
    );
    expect(api.getResearchPlan).toHaveBeenCalledWith({
      job_id: 3,
      weekly_hours: 3,
      weeks: 2,
      goal: "project",
      learning_style: "hands_on",
      language: "zh-CN",
    });

    expect(
      await screen.findByText(
        "推荐原因：覆盖技能：Docker；4 小时，适合 beginner 水平。",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("交付物")).toBeInTheDocument();
  });

  it("gives a Year 1 student a no-CV starting plan with official opportunities", async () => {
    const user = userEvent.setup();
    renderWithProviders(<StarterPlanner mode="new" />);
    await user.type(
      screen.getByLabelText("你想探索什么方向？"),
      "我是大一学生，对 AI 和金融感兴趣。",
    );
    await user.click(screen.getByRole("button", { name: "生成我的起步计划" }));
    await waitFor(() =>
      expect(api.getStarterPlan).toHaveBeenCalledWith({
        interest: "我是大一学生，对 AI 和金融感兴趣。",
        weekly_hours: 3,
        weeks: 4,
        experience_level: "none",
        goal: "explore",
        preferred_formats: ["project"],
        experience_level_other: "",
        goal_other: "",
        preferred_format_other: "",
        language: "zh-CN",
      }),
    );
    expect(
      await screen.findByText("Start with a real research habit."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Docker Get Started/ }),
    ).toHaveAttribute("href", resource.url);
  });

  it("restores the complete saved starter plan instead of a static summary", async () => {
    api.getSavedStarterPlan.mockResolvedValue({
      id: 4,
      focus: "quant",
      headline: "Start with a real research habit.",
      first_action: "Write a hypothesis before coding.",
      milestones: ["Explore one official resource"],
      resources: [resource],
      used_fallback: false,
      created_at: "2026",
      updated_at: "2026",
    });
    renderWithProviders(<ResourcePlanPage />);
    expect(await screen.findByText("你已保存的起步计划")).toBeInTheDocument();
    expect(
      screen.getByText("Explore one official resource"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Docker Get Started/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "下载学习计划" }),
    ).toBeInTheDocument();
  });

  it("regenerates from the saved starter plan without requesting a job plan", async () => {
    const user = userEvent.setup();
    const savedStarter = {
      id: 4,
      interest: "我是大一学生，对金融和 AI 感兴趣",
      focus: "quant",
      headline: "Start from my saved interest",
      first_action: "Write a hypothesis.",
      milestones: ["Explore one official resource"],
      resources: [resource],
      used_fallback: false,
      created_at: "2026",
      updated_at: "2026",
    };
    api.getSavedStarterPlan.mockResolvedValue(savedStarter);
    api.refineStarterPlan.mockResolvedValue({
      ...savedStarter,
      headline: "Refined from saved interest",
    });
    renderWithProviders(<ResourcePlanPage initialJobId={3} />);

    await screen.findByText("Start from my saved interest");
    await user.click(screen.getByRole("button", { name: /已保存的起步计划/ }));
    await user.click(screen.getByRole("button", { name: "生成学习计划" }));

    await waitFor(() =>
      expect(api.refineStarterPlan).toHaveBeenCalledWith(
        4,
        expect.objectContaining({ weekly_hours: 3, weeks: 2 }),
      ),
    );
    expect(api.getResearchPlan).not.toHaveBeenCalled();
    expect(screen.queryByText("Research brief")).not.toBeInTheDocument();
  });

  it("lets the user edit a saved starter plan and persists it", async () => {
    const user = userEvent.setup();
    api.getSavedStarterPlan.mockResolvedValue({
      id: 4,
      focus: "quant",
      headline: "Original plan",
      first_action: "Original action",
      milestones: ["Original step"],
      resources: [resource],
      used_fallback: false,
      created_at: "2026",
      updated_at: "2026",
    });
    renderWithProviders(<ResourcePlanPage />);
    await screen.findByText("Original plan");
    await user.click(screen.getByRole("button", { name: "编辑计划" }));
    const summary = screen.getByLabelText("计划摘要");
    await user.clear(summary);
    await user.type(summary, "Updated plan");
    await user.click(screen.getByRole("button", { name: "保存修改" }));
    await waitFor(() =>
      expect(api.updateStarterPlan).toHaveBeenCalledWith(
        4,
        expect.objectContaining({ headline: "Updated plan" }),
      ),
    );
    expect(await screen.findByText("Updated plan")).toBeInTheDocument();
  });

  it("lets the user edit or delete an AI research brief instead of treating it as final", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ResourcePlanPage initialJobId={3} />);
    await user.click(screen.getByRole("button", { name: "生成学习计划" }));
    await screen.findByText("Research brief");
    await user.click(screen.getByRole("button", { name: "编辑方案" }));
    const summary = screen.getByLabelText("方案总结");
    await user.clear(summary);
    await user.type(summary, "My edited research plan");
    await user.click(screen.getByRole("button", { name: "保存修改" }));
    expect(
      await screen.findByText("My edited research plan"),
    ).toBeInTheDocument();
    expect(api.updateResearchPlan).toHaveBeenCalledWith(
      12,
      expect.objectContaining({ profile_summary: "My edited research plan" }),
    );
    await user.click(screen.getByRole("button", { name: "删除方案" }));
    expect(api.deleteResearchPlan).toHaveBeenCalledWith(12);
    expect(
      screen.queryByText("My edited research plan"),
    ).not.toBeInTheDocument();
  });

  it("uses a user-facing target and updates completion state", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ResourcePlanPage initialJobId={3} />);

    await user.click(screen.getByRole("button", { name: "生成学习计划" }));
    await screen.findByText("Docker Get Started");

    await user.click(screen.getByRole("button", { name: "标记完成" }));
    await waitFor(() =>
      expect(api.completeResource).toHaveBeenCalledWith(4, true),
    );
    expect(
      await screen.findByRole("button", { name: "已完成" }),
    ).toBeInTheDocument();
  });

  it("requires user-authored evidence before creating an unconfirmed experience draft", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ResourcePlanPage initialJobId={3} />);
    await user.click(screen.getByRole("button", { name: "生成学习计划" }));
    await screen.findByText("Docker Get Started");
    await user.click(screen.getByRole("button", { name: "标记完成" }));
    const reflection = await screen.findByLabelText(
      "你完成了什么？：Docker Get Started",
    );
    await user.type(
      reflection,
      "I built the API, added a health check, and wrote a README.",
    );
    await user.click(
      screen.getByRole("button", { name: "创建待确认经历草稿" }),
    );
    await waitFor(() =>
      expect(api.createExperienceDraft).toHaveBeenCalledWith(
        4,
        "I built the API, added a health check, and wrote a README.",
      ),
    );
    expect(
      await screen.findByText("草稿已进入 Experience Bank，等待你编辑和确认。"),
    ).toBeInTheDocument();
  });

  it("checks a curated link and sends a user-authored issue report", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ResourcePlanPage initialJobId={3} />);
    await user.click(screen.getByRole("button", { name: "生成学习计划" }));
    await screen.findByText("Docker Get Started");
    await user.click(screen.getByRole("button", { name: "检查链接" }));
    await waitFor(() =>
      expect(api.checkResourceHealth).toHaveBeenCalledWith(4),
    );
    expect(await screen.findByText("链接正常")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "报告问题" }));
    await user.selectOptions(
      screen.getByLabelText("问题类型"),
      "outdated_content",
    );
    await user.type(
      screen.getByLabelText("发生了什么？"),
      "The course page uses an obsolete exercise.",
    );
    await user.click(screen.getByRole("button", { name: "提交反馈" }));
    await waitFor(() =>
      expect(api.submitResourceFeedback).toHaveBeenCalledWith(
        4,
        "outdated_content",
        "The course page uses an obsolete exercise.",
      ),
    );
    expect(
      await screen.findByText("感谢，你的反馈已记录。"),
    ).toBeInTheDocument();
  });
});
