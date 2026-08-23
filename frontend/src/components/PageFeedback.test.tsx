import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/render";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PageFeedback } from "./PageFeedback";

describe("PageFeedback", () => {
  it("announces errors and runs the recovery action", async () => {
    const retry = vi.fn();
    const user = userEvent.setup();

    renderWithProviders(
      <PageFeedback
        kind="error"
        message="网络连接失败"
        actionLabel="重试"
        onAction={retry}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("网络连接失败");

    await user.click(screen.getByRole("button", { name: "重试" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
