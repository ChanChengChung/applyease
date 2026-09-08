import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getRecommendations: vi.fn(),
  getStarterPlan: vi.fn(),
  getSavedStarterPlan: vi.fn(),
  listStarterPlans: vi.fn(),
  deleteStarterPlan: vi.fn(),
  updateStarterPlan: vi.fn(),
  refineStarterPlan: vi.fn(),
  getResearchPlan: vi.fn(),
  getSavedResearchPlan: vi.fn(),
  updateResearchPlan: vi.fn(),
  deleteResearchPlan: vi.fn(),
  completeResource: vi.fn(),
  createExperienceDraft: vi.fn(),
}));
vi.mock("../../services/resourceApi", () => api);
const jobsApi = vi.hoisted(() => ({ listJobs: vi.fn() }));
vi.mock("../../services/jobApi", () => jobsApi);
const materialsApi = vi.hoisted(() => ({ listMaterials: vi.fn() }));
vi.mock("../../services/materialApi", () => materialsApi);
const applicationsApi = vi.hoisted(() => ({ getLatestApplication: vi.fn() }));
vi.mock("../../services/applicationApi", () => applicationsApi);
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
    materialsApi.listMaterials.mockResolvedValue([
      {
        id: 31,
        job_id: 3,
        material_type: "resume",
        text: "Tailored resume for the role",
        character_count: 30,
        fact_check_passed: true,
        warnings: [],
        sources: [],
        generation_method: "rules",
        created_at: "2026",
      },
    ]);
    applicationsApi.getLatestApplication.mockResolvedValue({
      id: 41,
      job_id: 3,
      raw_text: "Why this role?",
      questions: [{ id: 51, application_id: 41, question: "Why this role?", question_type: "free_text", max_characters: 300, required: true, answer: {}, created_at: "2026" }],
      created_at: "2026",
    });
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
    api.listStarterPlans.mockRejectedValue(new Error("No saved starter plans"));
    api.deleteStarterPlan.mockResolvedValue(undefined);
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
  });

  it("loads explainable recommendations using user filters", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ResourcePlanPage />);

    await screen.findByRole("button", { name: /我要申请的职位/ });
    await user.click(screen.getByRole("button", { name: /我要申请的职位/ }));
    await user.selectOptions(screen.getByLabelText("选择已分析职位"), "3");
    expect(screen.getByText("该职位已准备的申请资料")).toBeInTheDocument();
    expect(screen.getByText("Why this role?")).toBeInTheDocument();
    expect(screen.queryByText("你想达成什么？")).not.toBeInTheDocument();
    expect(screen.queryByText("你希望怎样学习？")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("你的水平"), "beginner");
    await user.click(screen.getByLabelText("只看免费资源"));
    await user.click(screen.getByRole("button", { name: "生成学习·补强计划" }));

    await waitFor(() =>
      expect(api.getRecommendations).toHaveBeenCalledWith(3, {
        level: "beginner",
        max_total_hours: 6,
        free_only: true,
        limit: 12,
        goal: "skills",
        language: "zh-CN",
      }),
    );
    expect(api.getResearchPlan).toHaveBeenCalledWith({
      job_id: 3,
      weekly_hours: 3,
      weeks: 2,
      goal: "skills",
      learning_style: "guided",
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
      await screen.findByText("Write a hypothesis before coding."),
    ).toBeInTheDocument();
    // The generated plan is also indexed in the saved-plan folder so it can
    // be revisited after returning to the starting page.
    expect(screen.getByText("Start with a real research habit.")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Docker Get Started/ }),
    ).toHaveAttribute("href", resource.url);
  });

  it("keeps multiple generated starter plans in the folder and supports deletion", async () => {
    const user = userEvent.setup();
    const older = {
      id: 21,
      interest: "我对化学感兴趣，想探索实验方向",
      focus: "chemistry",
      headline: "Explore chemistry safely",
      first_action: "Read one introductory lab guide.",
      milestones: ["Read a guide"],
      resources: [resource],
      used_fallback: false,
      created_at: "2026",
      updated_at: "2026",
    };
    const newer = {
      id: 22,
      interest: "我对数学建模感兴趣，想从基础开始",
      focus: "mathematics",
      headline: "Start with a modelling question",
      first_action: "Write one testable question.",
      milestones: ["Write a question"],
      resources: [resource],
      used_fallback: false,
      created_at: "2026",
      updated_at: "2026",
    };
    api.listStarterPlans.mockResolvedValue([older]);
    api.getStarterPlan.mockResolvedValue(newer);
    api.deleteStarterPlan.mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderWithProviders(<StarterPlanner mode="new" />);
    expect((await screen.findAllByText(older.interest)).length).toBeGreaterThan(0);
    const prompt = screen.getByLabelText("你想探索什么方向？");
    await user.clear(prompt);
    await user.type(prompt, newer.interest);
    await user.click(screen.getByRole("button", { name: "生成我的起步计划" }));

    expect((await screen.findAllByText(newer.interest)).length).toBeGreaterThan(0);
    expect((screen.getAllByText(older.interest)).length).toBeGreaterThan(0);
    await user.click(
      screen.getByRole("button", { name: `删除已保存计划: ${older.interest}` }),
    );
    await waitFor(() => expect(api.deleteStarterPlan).toHaveBeenCalledWith(older.id));
    expect(screen.queryByText(older.interest)).not.toBeInTheDocument();
    expect((screen.getAllByText(newer.interest)).length).toBeGreaterThan(0);
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
    const savedStarterButton = await screen.findByRole("button", {
      name: /已保存的起步计划/,
    });
    await waitFor(() => expect(savedStarterButton).not.toBeDisabled());
    await userEvent.setup().click(savedStarterButton);
    expect(await screen.findByText("你已保存的起步计划")).toBeInTheDocument();
    expect(
      screen.getByText("Explore one official resource"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Docker Get Started/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "下载学习·补强计划" }),
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

    const savedStarterButton = await screen.findByRole("button", {
      name: /已保存的起步计划/,
    });
    await waitFor(() => expect(savedStarterButton).not.toBeDisabled());
    expect(screen.queryByText("Start from my saved interest")).not.toBeInTheDocument();
    await user.click(savedStarterButton);
    await screen.findByText("我是大一学生，对金融和 AI 感兴趣");
    await user.click(screen.getByRole("button", { name: "生成学习·补强计划" }));

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
    const savedStarterButton = await screen.findByRole("button", {
      name: /已保存的起步计划/,
    });
    await waitFor(() => expect(savedStarterButton).not.toBeDisabled());
    await user.click(savedStarterButton);
    await screen.findByText("Original action");
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
    expect(screen.getByText("Updated plan")).toBeInTheDocument();
  });

  it("lets the user edit or delete an AI research brief instead of treating it as final", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ResourcePlanPage initialJobId={3} />);
    await user.click(screen.getByRole("button", { name: "生成学习·补强计划" }));
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

    await user.click(screen.getByRole("button", { name: "生成学习·补强计划" }));
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
    await user.click(screen.getByRole("button", { name: "生成学习·补强计划" }));
    await screen.findByText("Docker Get Started");
    await user.click(screen.getByRole("button", { name: "标记完成" }));
    const reflection = await screen.findByLabelText(
      "你完成了什么？：Docker Get Started",
    );
    const draftButton = screen.getByRole("button", { name: "创建待确认经历草稿" });
    // The button remains actionable so the user receives the inline minimum
    // length guidance instead of seeing a permanently disabled control.
    expect(draftButton).toBeEnabled();
    await user.click(draftButton);
    expect(await screen.findByText("创建草稿前，请至少描述 10 个字符的已完成工作。"))
      .toBeInTheDocument();
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

});
