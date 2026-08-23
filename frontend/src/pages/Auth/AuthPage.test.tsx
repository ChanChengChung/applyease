import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  forgotPassword: vi.fn(),
  resetPassword: vi.fn(),
  confirmEmail: vi.fn(),
  requestEmailVerification: vi.fn(),
  verifyMfaLogin: vi.fn(),
}));
vi.mock("../../services/authApi", () => api);
import { AuthPage } from "./AuthPage";

describe("AuthPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState({}, "", "/");

    api.login.mockResolvedValue({ user: { email_verified: true } });

    api.register.mockResolvedValue({
      user: { email_verified: true },
      session_ready: true,
    });

    api.forgotPassword.mockResolvedValue({
      message:
        "If the account exists, password reset instructions have been sent.",
      delivery_channel: "email",
    });

    api.resetPassword.mockResolvedValue({
      message: "Password reset. Sign in again on all devices.",
    });

    api.confirmEmail.mockResolvedValue({
      message: "Email verified. You can now sign in.",
    });

    api.requestEmailVerification.mockResolvedValue({
      message: "Verification sent.",
    });
  });

  it("logs in and reports completion", async () => {
    const user = userEvent.setup();
    const done = vi.fn();
    renderWithProviders(<AuthPage onAuthenticated={done} />);

    await user.type(screen.getByLabelText("邮箱"), "student@example.com");
    await user.type(screen.getByLabelText("密码"), "secure-pass");
    await user.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() =>
      expect(api.login).toHaveBeenCalledWith(
        "student@example.com",
        "secure-pass",
      ),
    );
    expect(done).toHaveBeenCalled();
  });

  it("requires a second factor when the login challenge requests it", async () => {
    api.login.mockResolvedValueOnce({
      user: { email_verified: true },
      mfa_required: true,
      mfa_token: "mfa-token-value-long-enough-to-be-valid",
    });
    api.verifyMfaLogin.mockResolvedValueOnce({
      user: { email_verified: true },
    });
    const user = userEvent.setup();
    const done = vi.fn();
    renderWithProviders(<AuthPage onAuthenticated={done} />);
    await user.type(screen.getByLabelText("邮箱"), "student@example.com");
    await user.type(screen.getByLabelText("密码"), "secure-pass");
    await user.click(screen.getByRole("button", { name: "登录" }));
    await user.type(await screen.findByLabelText("验证器或恢复码"), "123456");
    await user.click(screen.getByRole("button", { name: "验证并继续" }));
    await waitFor(() =>
      expect(api.verifyMfaLogin).toHaveBeenCalledWith(
        "mfa-token-value-long-enough-to-be-valid",
        "123456",
      ),
    );
    expect(done).toHaveBeenCalled();
  });

  it("switches to registration and displays API errors", async () => {
    api.register.mockRejectedValueOnce(new Error("邮箱已注册"));
    const user = userEvent.setup();
    renderWithProviders(<AuthPage onAuthenticated={vi.fn()} />);

    await user.click(screen.getByRole("link", { name: "没有账号？注册" }));
    await user.type(screen.getByLabelText("邮箱"), "student@example.com");
    await user.type(screen.getByLabelText("密码"), "secure-passphrase");
    await user.type(screen.getByLabelText("确认密码"), "secure-passphrase");
    await user.click(screen.getByRole("button", { name: "创建账号" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("邮箱已注册");
  });

  it("keeps an unverified registration on the verification screen", async () => {
    api.register.mockResolvedValueOnce({ user: { email_verified: false } });

    const user = userEvent.setup();
    const done = vi.fn();
    renderWithProviders(<AuthPage onAuthenticated={done} />);

    await user.click(screen.getByRole("link", { name: "没有账号？注册" }));

    await user.type(screen.getByLabelText("邮箱"), "new@example.com");

    await user.type(screen.getByLabelText("密码"), "secure-passphrase");

    await user.type(screen.getByLabelText("确认密码"), "secure-passphrase");

    await user.click(screen.getByRole("button", { name: "创建账号" }));

    expect(await screen.findByText(/请打开验证邮件/)).toBeInTheDocument();
    expect(done).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "重发验证邮件" }));

    await waitFor(() =>
      expect(api.requestEmailVerification).toHaveBeenCalledWith(
        "new@example.com",
      ),
    );
  });

  it("requests a password reset without revealing account existence", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuthPage onAuthenticated={vi.fn()} />);

    await user.click(screen.getByRole("link", { name: "忘记密码" }));

    await user.type(screen.getByLabelText("邮箱"), "student@example.com");

    await user.click(screen.getByRole("button", { name: "发送重置说明" }));

    expect(await screen.findByText(/重置说明已发送/)).toBeInTheDocument();

    expect(api.forgotPassword).toHaveBeenCalledWith("student@example.com");
  });

  it("can resend a reset code from the six-digit-code screen", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuthPage onAuthenticated={vi.fn()} />);

    await user.click(screen.getByRole("link", { name: "忘记密码" }));
    await user.type(screen.getByLabelText("邮箱"), "student@example.com");
    await user.click(screen.getByRole("button", { name: "发送重置说明" }));
    await user.click(
      await screen.findByRole("button", { name: "输入重置验证码" }),
    );

    expect(screen.getByLabelText("六位重置验证码")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重新发送验证码" }));

    await waitFor(() => expect(api.forgotPassword).toHaveBeenCalledTimes(2));
    expect(api.forgotPassword).toHaveBeenLastCalledWith("student@example.com");
  });

  it("validates and submits matching passwords from a reset link", async () => {
    window.history.replaceState(
      {},
      "",
      "/#reset_token=valid-reset-token-value-that-is-long-enough",
    );

    const user = userEvent.setup();
    renderWithProviders(<AuthPage onAuthenticated={vi.fn()} />);

    await user.type(screen.getByLabelText("新密码"), "new-secure-password");

    await user.type(screen.getByLabelText("确认新密码"), "different-password");

    await user.click(screen.getByRole("button", { name: "重置密码" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "两次输入的密码不一致",
    );

    await user.clear(screen.getByLabelText("确认新密码"));
    await user.type(screen.getByLabelText("确认新密码"), "new-secure-password");

    await user.click(screen.getByRole("button", { name: "重置密码" }));

    await waitFor(() =>
      expect(api.resetPassword).toHaveBeenCalledWith(
        "valid-reset-token-value-that-is-long-enough",
        "new-secure-password",
      ),
    );

    expect(
      await screen.findByRole("heading", { name: "密码重置完成" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("密码已重置完成。你现在可以返回登录。"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "返回登录" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "重发验证邮件" }),
    ).not.toBeInTheDocument();
  });

  it("confirms a verification link automatically", async () => {
    window.history.replaceState(
      {},
      "",
      "/#verify_token=valid-verification-token-value-long-enough",
    );

    renderWithProviders(<AuthPage onAuthenticated={vi.fn()} />);

    await waitFor(() =>
      expect(api.confirmEmail).toHaveBeenCalledWith(
        "valid-verification-token-value-long-enough",
      ),
    );

    expect(await screen.findByText(/Email verified/)).toBeInTheDocument();
    expect(window.location.search).toBe("");
    expect(window.location.hash).toBe("");
  });

  it("prevents registration when its two password entries differ", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuthPage onAuthenticated={vi.fn()} />);
    await user.click(screen.getByRole("link", { name: "没有账号？注册" }));
    await user.type(screen.getByLabelText("邮箱"), "student@example.com");
    await user.type(screen.getByLabelText("密码"), "secure-passphrase");
    await user.type(screen.getByLabelText("确认密码"), "another-passphrase");
    await user.click(screen.getByRole("button", { name: "创建账号" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "两次输入的密码不一致",
    );
    expect(api.register).not.toHaveBeenCalled();
  });

  it("localizes API error codes instead of rendering raw error details", async () => {
    api.login.mockRejectedValueOnce({
      code: "auth_error_invalid_credentials",
      message: "Invalid email or password",
    });
    const user = userEvent.setup();
    renderWithProviders(<AuthPage onAuthenticated={vi.fn()} />);
    await user.type(screen.getByLabelText("邮箱"), "student@example.com");
    await user.type(screen.getByLabelText("密码"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "登录" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "登录信息不正确。请检查邮箱拼写与 Caps Lock，或使用“忘记密码”。为保护账号安全，我们不会显示该邮箱是否已注册。",
    );
  });

  it("uses the selected-language password visibility labels", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuthPage onAuthenticated={vi.fn()} />);
    const toggle = screen.getByRole("button", { name: "显示密码" });
    await user.click(toggle);
    expect(
      screen.getByRole("button", { name: "隐藏密码" }),
    ).toBeInTheDocument();
  });

  it("keeps the selected language in the shared URL setting before sign-in", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AuthPage onAuthenticated={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "繁" }));
    expect(window.location.pathname).toBe("/zh-tw");
    expect(screen.getByRole("heading", { name: "登入" })).toBeInTheDocument();
  });
});
