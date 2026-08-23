import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../../test/render";

const resourceApi = vi.hoisted(() => ({ getStarterPlan: vi.fn() }));
vi.mock("../../services/resourceApi", () => resourceApi);
import { WelcomePage } from "./WelcomePage";

describe("WelcomePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resourceApi.getStarterPlan.mockResolvedValue({
      id: 1,
      headline: "Start small",
      first_action: "Read one guide",
      milestones: [],
      resources: [],
      used_fallback: false,
    });
  });

  it("shows the entry choice even when the user already has evidence", async () => {
    const onOpenExperienceBank = vi.fn();
    const user = userEvent.setup();
    renderWithProviders(
      <WelcomePage
        onOpenExperienceBank={onOpenExperienceBank}
        onOpenLearningPlan={vi.fn()}
      />,
    );
    expect(await screen.findByText("我们该打造什么？")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /我已有相关经历/ }));
    expect(onOpenExperienceBank).toHaveBeenCalledTimes(1);
  });

  it("keeps a new student in the dedicated welcome flow", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <WelcomePage
        onOpenExperienceBank={vi.fn()}
        onOpenLearningPlan={vi.fn()}
      />,
    );
    await user.click(await screen.findByRole("button", { name: /我刚刚开始/ }));
    expect(
      screen.getByText("还没有 CV？先建立第一份可验证成果"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "返回" }));
    expect(await screen.findByText("我们该打造什么？")).toBeInTheDocument();
  });
});
