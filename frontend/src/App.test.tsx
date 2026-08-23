import { screen } from "@testing-library/react";
import { renderWithProviders } from "./test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const dashboard = vi.hoisted(() => ({ getDashboardSummary: vi.fn() }));
const tracker = vi.hoisted(() => ({
  listTracked: vi.fn(),
  getTrackerSummary: vi.fn(),
  getTrackerReminders: vi.fn(),
  downloadTrackerCalendar: vi.fn(),
  saveCalendarDownload: vi.fn(),
  createTracked: vi.fn(),
  updateTracked: vi.fn(),
  deleteTracked: vi.fn(),
}));
vi.mock("./services/dashboardApi", () => dashboard);
vi.mock("./services/trackerApi", () => tracker);
import { App } from "./App";

const summary = {
  experience_total: 1,
  confirmed_experiences: 1,
  pending_experiences: 0,
  job_total: 1,
  latest_job: { id: 7, title: "AI Intern", company: "Polymer" },
  material_count: 2,
  material_types: ["resume", "cover_letter"],
  latest_material_type: "cover_letter",
  application_id: 9,
  questions_total: 2,
  answers_ready: 2,
  tracker_total: 0,
  active_applications: 0,
  upcoming_deadlines: [],
  steps: [
    {
      key: "profile",
      label: "经历库",
      description: "确认事实",
      status: "complete",
      target: "profile",
    },
    {
      key: "jobs",
      label: "职位分析",
      description: "分析",
      status: "complete",
      target: "jobs",
    },
    {
      key: "builder",
      label: "申请材料",
      description: "材料",
      status: "complete",
      target: "builder",
    },
    {
      key: "form",
      label: "申请问题",
      description: "问题",
      status: "complete",
      target: "form",
    },
    {
      key: "tracker",
      label: "申请追踪",
      description: "追踪",
      status: "current",
      target: "tracker",
    },
  ],
  next_action: {
    title: "加入申请追踪",
    description: "保存申请",
    target: "tracker",
  },
};

describe("App workflow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.scrollTo = vi.fn();
    dashboard.getDashboardSummary.mockResolvedValue(summary);
    tracker.listTracked.mockResolvedValue([]);
    tracker.getTrackerSummary.mockResolvedValue({
      total: 0,
      by_status: {},
      active: 0,
      overdue: 0,
      follow_ups_due: 0,
    });
    tracker.getTrackerReminders.mockResolvedValue([]);
    tracker.createTracked.mockResolvedValue({ id: 1 });
  });

  it("keeps the welcome choice as the signed-in app entry point", async () => {
    renderWithProviders(<App />);

    expect(await screen.findByText("我们该打造什么？")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /我刚刚开始/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /我已有相关经历/ })).toBeInTheDocument();
  });
});
