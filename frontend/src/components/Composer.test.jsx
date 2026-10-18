import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Composer from "./Composer";

const setup = (props = {}) => {
  const onSend = vi.fn();
  const onStop = vi.fn();
  render(<Composer value="hello" onChange={() => {}} onSend={onSend} onStop={onStop} {...props} />);
  return { onSend, onStop, box: screen.getByLabelText("Message") };
};

describe("Composer", () => {
  it("sends on Enter but not on Shift+Enter", () => {
    const { onSend, box } = setup();
    fireEvent.keyDown(box, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("disables send for an empty message", () => {
    setup({ value: "   " });
    expect(screen.getByLabelText("Send message")).toBeDisabled();
  });

  it("shows a Stop button while streaming and does not send on Enter", () => {
    const { onSend, onStop, box } = setup({ streaming: true });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText("Stop generating"));
    expect(onStop).toHaveBeenCalled();
  });
});
