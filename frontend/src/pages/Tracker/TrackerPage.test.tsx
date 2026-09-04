import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  listTracked: vi.fn(),
  getTrackerSummary: vi.fn(),
  getTrackerReminders: vi.fn(),
  getApplicationWorkspace: vi.fn(),
  downloadTrackerCalendar: vi.fn(),
  saveCalendarDownload: vi.fn(),
  createTracked: vi.fn(),
  updateTracked: vi.fn(),
  coachInterviewReview: vi.fn(),
  deleteTracked: vi.fn(),
}));
vi.mock("../../services/trackerApi", () => api);
const jobApi = vi.hoisted(() => ({ listJobs: vi.fn() }));
vi.mock("../../services/jobApi", () => jobApi);
import { TrackerPage } from "./TrackerPage";

const record = {
  id: 1,
  job_id: 3,
  company: "Polymer",
  role: "Quant Intern",
  status: "saved",
  deadline: "2026-08-20",
  interview_date: "",
  follow_up_at: "2026-08-22",
  notes: "Email recruiter",
  created_at: "2026-08-01",
  is_overdue: false,
  is_follow_up_due: false,
  next_action: "等待申请结果",
};

describe("TrackerPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listTracked.mockResolvedValue([record]);
    api.getTrackerSummary.mockResolvedValue({
      total: 1,
      by_status: { saved: 1 },
      active: 1,
      overdue: 0,
      follow_ups_due: 0,
      next_action: record,
    });
    api.getTrackerReminders.mockResolvedValue([
      {
        application_id: 1,
        kind: "follow_up",
        due_date: "2026-08-22",
        state: "upcoming",
        company: "Polymer",
        role: "Quant Intern",
        title: "跟进申请：Polymer · Quant Intern",
      },
    ]);
    api.getApplicationWorkspace.mockResolvedValue({
      application_id: 1,
      job_id: 3,
      match_score: 72,
      evidence_count: 2,
      missing_skills: ["C++"],
      material_types: ["resume"],
      questions_total: 2,
      answers_ready: 1,
      material_versions: [
        { id: 8, material_type: "resume", fact_check_passed: true },
      ],
      learning_plan_id: 19,
      learning_plan_steps: 3,
    });
    api.downloadTrackerCalendar.mockResolvedValue({
      blob: new Blob(["ics"]),
      filename: "test.ics",
    });
    api.createTracked.mockResolvedValue(record);
    api.updateTracked.mockResolvedValue({ ...record, status: "interview" });
    api.coachInterviewReview.mockResolvedValue({
      ...record,
      interview_review: {
        questions: "How?",
        strengths: "Clear",
        improvements: "Structure",
        next_steps: "Practise",
        ai_feedback: {
          summary: "Use a structured answer.",
          strengths: [],
          improvements: ["Name the result"],
          suggested_answer_points: [],
          follow_up_questions: [],
          generation_method: "rules",
          warnings: [],
        },
      },
    });
    api.deleteTracked.mockResolvedValue(undefined);
    jobApi.listJobs.mockResolvedValue([
      {
        id: 8,
        company: "Jane Street",
        title: "Software Engineer Internship",
        description: "Build reliable systems with a collaborative team.",
        required_skills: ["Programming"],
        preferred_skills: [],
        responsibilities: [],
        qualifications: [],
        created_at: "2026-08-20",
      },
    ]);
  });

  it("creates a record and sends filters", async () => {
    const user = userEvent.setup();
    renderWithProviders(<TrackerPage />);
    await screen.findByText("Polymer");

    await user.click(screen.getByRole("button", { name: "手动新增" }));
    await user.type(screen.getByLabelText("添加公司"), "NewCo");
    await user.type(screen.getByLabelText("添加职位"), "Data Intern");

    await user.click(screen.getByRole("button", { name: "添加申请" }));

    await waitFor(() =>
      expect(api.createTracked).toHaveBeenCalledWith(
        expect.objectContaining({
          company: "NewCo",
          role: "Data Intern",
          status: "saved",
        }),
      ),
    );

    await user.selectOptions(screen.getByLabelText("筛选状态"), "interview");

    await waitFor(() =>
      expect(api.listTracked).toHaveBeenLastCalledWith({
        status: "interview",
        sort: "deadline",
      }),
    );
  });

  it("stays on the tracker after adding an application", async () => {
    const user = userEvent.setup();
    renderWithProviders(<TrackerPage />);
    await screen.findByText("Polymer");

    await user.click(screen.getByRole("button", { name: "手动新增" }));
    await user.type(screen.getByLabelText("添加公司"), "StayCo");
    await user.type(screen.getByLabelText("添加职位"), "Analyst");
    await user.click(screen.getByRole("button", { name: "添加申请" }));

    await waitFor(() => expect(api.createTracked).toHaveBeenCalled());
    expect(screen.getByRole("heading", { name: "添加申请" })).toBeInTheDocument();
  });

  it("imports an analyzed role from the personal workspace into tracking", async () => {
    const user = userEvent.setup();
    renderWithProviders(<TrackerPage />);
    await screen.findByText("Polymer");

    await user.click(screen.getByRole("button", { name: "从个人工作台导入" }));
    await user.selectOptions(screen.getByLabelText("已分析职位"), "8");

    expect(screen.getByLabelText("添加公司")).toHaveValue("Jane Street");
    expect(screen.getByLabelText("添加职位")).toHaveValue(
      "Software Engineer Internship",
    );
    await user.click(screen.getByRole("button", { name: "添加申请" }));

    await waitFor(() =>
      expect(api.createTracked).toHaveBeenCalledWith(
        expect.objectContaining({
          job_id: 8,
          company: "Jane Street",
          role: "Software Engineer Internship",
          status: "saved",
        }),
      ),
    );
  });

  it("edits and confirms deletion", async () => {
    const user = userEvent.setup();
    renderWithProviders(<TrackerPage />);
    await screen.findByText("Polymer");

    await user.click(screen.getByRole("button", { name: "编辑" }));
    await user.selectOptions(screen.getByLabelText("编辑状态"), "interview");
    await user.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() =>
      expect(api.updateTracked).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ status: "interview" }),
      ),
    );

    vi.spyOn(window, "confirm").mockReturnValue(false);
    await user.click(screen.getByRole("button", { name: "删除" }));
    expect(api.deleteTracked).not.toHaveBeenCalled();

    vi.mocked(window.confirm).mockReturnValue(true);
    await user.click(screen.getByRole("button", { name: "删除" }));
    await waitFor(() => expect(api.deleteTracked).toHaveBeenCalledWith(1));
  });

  it("files a saved role in the applied-jobs folder using persisted status", async () => {
    const user = userEvent.setup();
    api.updateTracked.mockResolvedValue({ ...record, status: "applied" });
    renderWithProviders(<TrackerPage />);
    await screen.findByText("Polymer");

    await user.click(
      screen.getByRole("button", { name: "标记已申请并归档" }),
    );

    await waitFor(() =>
      expect(api.updateTracked).toHaveBeenCalledWith(1, { status: "applied" }),
    );
  });

  it("shows reminders, changes their horizon, and exports a selected calendar", async () => {
    const user = userEvent.setup();
    renderWithProviders(<TrackerPage />);
    await screen.findByText("Polymer");
    expect(screen.getByText(/跟进申请：Polymer/)).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("未来范围"), "30");
    await waitFor(() =>
      expect(api.getTrackerReminders).toHaveBeenLastCalledWith(30),
    );
    await user.click(screen.getByRole("button", { name: "导出日历 (.ics)" }));
    await waitFor(() =>
      expect(api.downloadTrackerCalendar).toHaveBeenCalledWith(1),
    );
    expect(api.saveCalendarDownload).toHaveBeenCalledWith(
      expect.objectContaining({ filename: "test.ics" }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent("日历已下载");
  });

  it("opens and focuses the selected role's specific tracker record", async () => {
    const scrollIntoView = vi.fn();
    Element.prototype.scrollIntoView = scrollIntoView;

    renderWithProviders(
      <TrackerPage
        initialJob={{ id: 3, company: "Polymer", title: "Quant Intern" }}
      />,
    );

    expect(await screen.findByText("Polymer")).toBeInTheDocument();
    await waitFor(() =>
      expect(scrollIntoView).toHaveBeenCalledWith(
        expect.objectContaining({ behavior: "smooth", block: "start" }),
      ),
    );
    expect(screen.getByText("这份职位已准备的材料")).toBeInTheDocument();
    expect(screen.getByText("申请题回答：已完成 1/2")).toBeInTheDocument();
    expect(screen.getByText("补强计划：已保存 3 步")).toBeInTheDocument();
  });
});
