import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/render";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CVUploader } from "./CVUploader";

describe("CVUploader", () => {
  it("passes the selected CV to the upload handler", async () => {
    const user = userEvent.setup();
    const onUpload = vi.fn();

    const { container } = renderWithProviders(
      <CVUploader onUpload={onUpload} />,
    );

    const file = new File(["resume"], "CV.pdf", { type: "application/pdf" });

    await user.upload(container.querySelector("input")!, file);
    expect(onUpload).toHaveBeenCalledWith(file);
  });

  it("disables file selection while parsing", () => {
    const { container } = renderWithProviders(
      <CVUploader onUpload={vi.fn()} disabled />,
    );

    expect(screen.getByText("正在解析...")).toBeInTheDocument();
    expect(container.querySelector("input")).toBeDisabled();
  });
});
