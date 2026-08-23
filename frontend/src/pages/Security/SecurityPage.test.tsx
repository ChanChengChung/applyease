import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  checkSession: vi.fn(),
  getMfaStatus: vi.fn(),
  listSessions: vi.fn(),
  changePassword: vi.fn(),
  revokeSession: vi.fn(),
  downloadAccountData: vi.fn(),
  saveAccountDownload: vi.fn(),
  deleteAccount: vi.fn(),
  startMfaSetup: vi.fn(),
  confirmMfaSetup: vi.fn(),
  rotateRecoveryCodes: vi.fn(),
  disableMfa: vi.fn(),
}));
vi.mock("../../services/authApi", () => api);
import { SecurityPage } from "./SecurityPage";

describe("SecurityPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.checkSession.mockResolvedValue({
      email: "student@example.com",
      email_verified: true,
    });
    api.getMfaStatus.mockResolvedValue({
      enabled: false,
      recovery_codes_remaining: 0,
    });
    api.listSessions.mockResolvedValue([
      { id: "current", current: true, last_seen_at: "2026-08-18T10:00:00" },
      { id: "other", current: false, last_seen_at: "2026-08-17T10:00:00" },
    ]);
    api.changePassword.mockResolvedValue({ message: "Password changed." });
    api.revokeSession.mockResolvedValue(undefined);
    api.downloadAccountData.mockResolvedValue({
      blob: new Blob(["zip"]),
      filename: "data.zip",
    });
    api.deleteAccount.mockResolvedValue(undefined);
  });
  it("shows account/devices and performs protected account actions", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SecurityPage />);
    await screen.findByText("student@example.com");
    await user.click(screen.getByRole("button", { name: "退出此设备" }));
    await waitFor(() =>
      expect(api.revokeSession).toHaveBeenCalledWith("other"),
    );
    await user.type(screen.getAllByLabelText("当前密码")[0], "old-password");
    await user.type(
      screen.getByLabelText("新密码"),
      "replacement-secure-password",
    );
    await user.type(
      screen.getByLabelText("确认新密码"),
      "replacement-secure-password",
    );
    await user.click(screen.getByRole("button", { name: "修改密码" }));
    await waitFor(() =>
      expect(api.changePassword).toHaveBeenCalledWith(
        "old-password",
        "replacement-secure-password",
      ),
    );
  });

  it("requires a password before exporting or deleting account data", async () => {
    const user = userEvent.setup();
    renderWithProviders(<SecurityPage />);
    await screen.findByText("student@example.com");
    expect(
      screen.getByRole("button", { name: "下载我的数据（.zip）" }),
    ).toBeDisabled();
    await user.type(
      screen.getByLabelText("用于导出或删除的密码"),
      "old-password",
    );
    await user.click(
      screen.getByRole("button", { name: "下载我的数据（.zip）" }),
    );
    await waitFor(() =>
      expect(api.downloadAccountData).toHaveBeenCalledWith("old-password", ""),
    );
    expect(api.saveAccountDownload).toHaveBeenCalled();
    await user.type(screen.getByLabelText("删除账号确认"), "DELETE");
    vi.spyOn(window, "confirm").mockReturnValue(false);
    await user.click(screen.getByRole("button", { name: "永久删除账号" }));
    expect(api.deleteAccount).not.toHaveBeenCalled();
  });
});
