import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "../test/render";
import { AdvisorAssistant } from "./AdvisorAssistant";

const api = vi.hoisted(() => ({
  getAdvisorHistory: vi.fn(),
  clearAdvisorHistory: vi.fn(),
  askAdvisor: vi.fn(),
}));

vi.mock("../services/advisorApi", () => api);

describe("AdvisorAssistant", () => {
  beforeEach(() => {
    api.getAdvisorHistory.mockResolvedValue([]);
    api.clearAdvisorHistory.mockResolvedValue(undefined);
    api.askAdvisor.mockResolvedValue({
      answer: "Review the confirmed project before exporting.",
      summary: "Review the confirmed project first.",
      sources: ["Experience: Project @ Lab"],
      evidence: [{
        type: "experience",
        id: 12,
        label: "Experience: Project @ Lab",
        detail: "A confirmed project",
        target_page: "profile",
      }],
      gaps: ["Add a measurable outcome"],
      next_actions: [{ label: "Open evidence bank", target_page: "profile" }],
      suggested_prompts: [],
      used_fallback: false,
      mode: "ai",
    });
  });

  it("offers page-aware prompts and renders grounded evidence/actions", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    HTMLElement.prototype.scrollIntoView = vi.fn();
    renderWithProviders(
      <AdvisorAssistant activePage="profile" onNavigate={onNavigate} />,
    );
    await user.click(screen.getByRole("button", { name: /Aira/ }));
    expect(screen.getByRole("button", { name: "你觉得我应该先突出哪段已确认经历？" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "你觉得我应该先突出哪段已确认经历？" }));
    expect(await screen.findByText("Review the confirmed project first.")).toBeInTheDocument();
    expect(screen.getByText("Experience: Project @ Lab")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Open evidence bank/ }));
    expect(onNavigate).toHaveBeenCalledWith("profile", undefined);
    // The composer must remain available after a long, structured response.
    expect(screen.getByRole("textbox", { name: /问问 Aira/ })).toBeInTheDocument();
    await waitFor(() => expect(api.askAdvisor).toHaveBeenCalled());
  });

  it("does not expose a compact chat control", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AdvisorAssistant activePage="profile" />);
    await user.click(screen.getByRole("button", { name: /Aira/ }));
    expect(screen.getByRole("textbox", { name: /问问 Aira/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /缩小聊天窗口|展开聊天窗口/ })).not.toBeInTheDocument();
  });

  it("can drag the collapsed launcher without opening it", () => {
    const { container } = renderWithProviders(<AdvisorAssistant activePage="profile" />);
    const launcher = screen.getByRole("button", { name: /Aira/ });
    fireEvent.pointerDown(launcher, { clientX: 1100, clientY: 700, pointerId: 1 });
    fireEvent.pointerMove(window, { clientX: 900, clientY: 500, pointerId: 1 });
    fireEvent.pointerUp(window, { clientX: 900, clientY: 500, pointerId: 1 });
    fireEvent.click(launcher);
    expect(screen.queryByRole("textbox", { name: /问问 Aira/ })).not.toBeInTheDocument();
    expect(container.querySelector(".advisor-shell")?.getAttribute("style")).toContain("left");
  });
});
