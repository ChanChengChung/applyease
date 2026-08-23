import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Sidebar } from "./Sidebar";
import { renderWithProviders } from "../test/render";

describe("Sidebar return and account controls", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/en");
  });

  it("keeps a discoverable route back to the welcome screen", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();

    renderWithProviders(
      <Sidebar
        activePage="profile"
        collapsed={false}
        onToggleCollapse={vi.fn()}
        onNavigate={onNavigate}
        authRequired={false}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: /Choose a starting point|重新选择起点|重新選擇起點/ }),
    );
    expect(onNavigate).toHaveBeenCalledWith("welcome");
  });

  it("offers the same welcome route inside the account menu", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();

    renderWithProviders(
      <Sidebar
        activePage="profile"
        collapsed
        onToggleCollapse={vi.fn()}
        onNavigate={onNavigate}
        authRequired
        onLogout={vi.fn()}
        currentUser={{
          id: 1,
          email: "student@example.com",
          email_verified: true,
          is_active: true,
          created_at: "2026-08-22T00:00:00Z",
        }}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Account menu|账号菜单|帳戶選單/i }));
    expect(screen.getByRole("menu")).toBeInTheDocument();

    await user.click(
      screen.getByRole("menuitem", { name: /Choose a starting point|重新选择起点|重新選擇起點/ }),
    );
    expect(onNavigate).toHaveBeenCalledWith("welcome");
  });
});
