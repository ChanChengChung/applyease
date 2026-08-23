import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AppErrorBoundary } from "./AppErrorBoundary";

function BrokenRoute(): never {
  throw new Error("simulated stale chunk");
}

describe("AppErrorBoundary", () => {
  it("replaces a crashed route with a recoverable reload action", async () => {
    const onReload = vi.fn();
    const user = userEvent.setup();

    // React intentionally reports the caught render error to console in tests.
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    render(
      <AppErrorBoundary
        title="Workspace needs a refresh"
        message="A newer version is available."
        reloadLabel="Reload"
        onReload={onReload}
      >
        <BrokenRoute />
      </AppErrorBoundary>,
    );
    consoleError.mockRestore();

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Workspace needs a refresh",
    );
    await user.click(screen.getByRole("button", { name: "Reload" }));
    expect(onReload).toHaveBeenCalledOnce();
  });
});
