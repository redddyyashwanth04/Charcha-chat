import { describe, expect, it } from "vitest";
import { groupByDate } from "./groupByDate";

const NOW = new Date("2026-10-18T12:00:00");
const conv = (id, iso, pinned = false) => ({ id, updated_at: iso, pinned });

describe("groupByDate", () => {
  it("buckets chats like Claude does and drops empty groups", () => {
    const groups = groupByDate(
      [
        conv(1, "2026-10-18T09:00:00"),
        conv(2, "2026-10-17T20:00:00"),
        conv(3, "2026-10-14T10:00:00"),
        conv(4, "2026-10-01T10:00:00"),
        conv(5, "2026-05-01T10:00:00"),
        conv(6, "2026-10-18T08:00:00", true),
      ],
      NOW
    );
    expect(groups.map((g) => g.label)).toEqual([
      "Pinned",
      "Today",
      "Yesterday",
      "Previous 7 days",
      "Previous 30 days",
      "Older",
    ]);
    expect(groups[0].items.map((c) => c.id)).toEqual([6]);
    expect(groups[1].items.map((c) => c.id)).toEqual([1]);
  });

  it("returns no groups for an empty list", () => {
    expect(groupByDate([], NOW)).toEqual([]);
  });
});
