import { describe, expect, it, vi } from "vitest";
import { createLineParser } from "./api";

describe("createLineParser", () => {
  it("emits one event per NDJSON line, even when lines are split across chunks", () => {
    const onEvent = vi.fn();
    const push = createLineParser(onEvent);
    push('{"type":"delta","text":"Hel');
    push('lo"}\n{"type":"done","id":4}\n');
    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent).toHaveBeenNthCalledWith(1, { type: "delta", text: "Hello" });
    expect(onEvent).toHaveBeenNthCalledWith(2, { type: "done", id: 4 });
  });

  it("ignores blank lines and waits for a complete line", () => {
    const onEvent = vi.fn();
    const push = createLineParser(onEvent);
    push("\n\n");
    push('{"type":"user","id":1}');
    expect(onEvent).not.toHaveBeenCalled();
    push("\n");
    expect(onEvent).toHaveBeenCalledWith({ type: "user", id: 1 });
  });
});
