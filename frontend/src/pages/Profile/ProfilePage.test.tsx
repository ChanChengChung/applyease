import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Experience } from "../../types/experience";

const api = vi.hoisted(() => ({
  listExperiences: vi.fn(),
  uploadCV: vi.fn(),
  updateExperience: vi.fn(),
  deleteExperience: vi.fn(),
  createExperience: vi.fn(),
  bulkConfirmExperiences: vi.fn(),
  getExperienceImpacts: vi.fn(),
}));
vi.mock("../../services/profileApi", () => api);

import { ProfilePage } from "./ProfilePage";

const item: Experience = {
  id: 1,
  title: "AI Developer",
  organization: "Novelflow",
  description: "Built a product",
  skills: ["React"],
  achievements: [],
  source_file: "CV.pdf",
  category: "project",
  confirmed: false,
};

async function openProjectFolder(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /打开项目与竞赛/ }));
}

describe("ProfilePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    api.listExperiences.mockResolvedValue([item]);

    api.updateExperience.mockResolvedValue(item);

    api.deleteExperience.mockResolvedValue(undefined);

    api.createExperience.mockResolvedValue({
      ...item,
      id: 99,
      title: "Manual project",
    });

    api.bulkConfirmExperiences.mockResolvedValue({
      updated: 1,
      missing_ids: [],
    });
    api.getExperienceImpacts.mockResolvedValue([]);
  });

  it("lets an experienced user return to the welcome choice", async () => {
    const user = userEvent.setup();
    const onReturnWelcome = vi.fn();
    renderWithProviders(<ProfilePage onReturnWelcome={onReturnWelcome} />);

    await user.click(await screen.findByRole("button", { name: "返回" }));
    expect(onReturnWelcome).toHaveBeenCalledTimes(1);
  });

  it("groups persisted experiences into folders and opens a two-column category view", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfilePage />);

    expect(
      await screen.findByText("你的申请证据库", { exact: false }),
    ).toBeInTheDocument();
    expect(screen.getByText("有 1 条待确认")).toBeInTheDocument();
    await openProjectFolder(user);

    expect(await screen.findByText("AI Developer")).toBeInTheDocument();
    expect(screen.getByText("待你核对")).toBeInTheDocument();

    expect(
      screen.getByText("你的申请证据库", { exact: false }),
    ).toHaveTextContent("1 条");
  });

  it("uploads a CV, reloads records, and reports successful extraction", async () => {
    const user = userEvent.setup();
    api.uploadCV.mockResolvedValue({ duplicate: false });

    const { container } = renderWithProviders(<ProfilePage />);
    await screen.findByText("你的申请证据库", { exact: false });

    const file = new File(["resume"], "CV.pdf", { type: "application/pdf" });

    await user.upload(container.querySelector('input[type="file"]')!, file);

    await waitFor(() => expect(api.uploadCV).toHaveBeenCalledWith(file));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "解析完成，请逐项确认经历",
    );

    expect(api.listExperiences).toHaveBeenCalledTimes(2);
  });

  it("puts CV import and manual entry together at the start of the evidence flow", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProfilePage />);

    expect(await screen.findByText("从一段真实经历开始")).toBeInTheDocument();
    expect(screen.getByText("通过 CV 导入")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "手动新增经历" }));
    expect(await screen.findByText("新增一条经历")).toBeInTheDocument();
  });

  it("surfaces upload failures without losing existing experiences", async () => {
    const user = userEvent.setup();
    api.uploadCV.mockRejectedValue(new Error("CV 解析超时"));

    const { container } = renderWithProviders(<ProfilePage />);
    await screen.findByText("你的申请证据库", { exact: false });

    await user.upload(
      container.querySelector('input[type="file"]')!,
      new File(["resume"], "CV.pdf", { type: "application/pdf" }),
    );

    expect(await screen.findByRole("status")).toHaveTextContent("CV 解析超时");

    await openProjectFolder(user);
    expect(screen.getByText("AI Developer")).toBeInTheDocument();
  });

  it("deletes only after confirmation and reloads the bank", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);

    renderWithProviders(<ProfilePage />);
    await screen.findByText("你的申请证据库", { exact: false });
    await openProjectFolder(user);

    await user.click(screen.getByRole("button", { name: "删除" }));

    await waitFor(() => expect(api.deleteExperience).toHaveBeenCalledWith(1));

    expect(api.listExperiences).toHaveBeenCalledTimes(2);

    expect(screen.getByRole("status")).toHaveTextContent("经历已删除");
  });

  it("searches the experience bank and sends the backend filter", async () => {
    const user = userEvent.setup();

    renderWithProviders(<ProfilePage />);
    await screen.findByText("你的申请证据库", { exact: false });
    await openProjectFolder(user);

    await user.type(screen.getByLabelText("搜索经历"), "Novelflow");

    await user.click(screen.getByRole("button", { name: "搜索" }));

    await waitFor(() =>
      expect(api.listExperiences).toHaveBeenLastCalledWith(
        expect.objectContaining({ query: "Novelflow", offset: 0 }),
      ),
    );
  });

  it("creates a manual experience and supports bulk confirmation", async () => {
    const user = userEvent.setup();

    renderWithProviders(<ProfilePage />);
    await screen.findByText("项目与竞赛");
    await openProjectFolder(user);

    await user.click(screen.getByRole("button", { name: "手动新增经历" }));

    await user.type(screen.getByLabelText("标题"), "Manual project");

    await user.click(screen.getByRole("button", { name: "保存经历" }));

    await waitFor(() =>
      expect(api.createExperience).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Manual project", confirmed: false }),
      ),
    );

    await user.click(
      screen.getByRole("checkbox", { name: "选择：AI Developer" }),
    );

    await user.click(screen.getByRole("button", { name: "确认已选（1）" }));

    await waitFor(() =>
      expect(api.bulkConfirmExperiences).toHaveBeenCalledWith([1]),
    );
    expect(screen.getByRole("button", { name: "确认已选（1）" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "确认已选（1）" }));
    await waitFor(() =>
      expect(api.bulkConfirmExperiences).toHaveBeenCalledTimes(2),
    );
  });
});
