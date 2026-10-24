import { describe, expect, it } from "vitest";
import { niceMax, stackedBars } from "../chart";

describe("niceMax", () => {
  it("rounds up to a readable axis maximum", () => {
    expect(niceMax(0)).toBe(4);
    expect(niceMax(3)).toBe(4);
    expect(niceMax(7)).toBe(8);
    expect(niceMax(37)).toBe(40);
    expect(niceMax(130)).toBe(200);
  });
});

describe("stackedBars", () => {
  const days = [
    { day: "2026-10-01", queries: 4, answered: 3 },
    { day: "2026-10-02", queries: 0, answered: 0 },
    { day: "2026-10-03", queries: 8, answered: 8 },
  ];

  it("stacks answered at the baseline and unanswered above, with a 2px gap", () => {
    const { bars, max } = stackedBars(days, { width: 300, height: 100, gap: 2 });
    expect(max).toBe(8);
    const [first, empty, full] = bars;
    expect(first.answered.y + first.answered.h).toBe(100); // anchored to baseline
    expect(first.answered.h).toBeCloseTo(37.5);
    expect(first.unanswered.y + first.unanswered.h).toBeCloseTo(first.answered.y - 2);
    expect(empty.answered.h).toBe(0);
    expect(empty.unanswered.h).toBe(0);
    expect(full.unanswered.h).toBe(0);
    expect(full.answered.h).toBe(100);
  });

  it("lays bars out left to right without overlap", () => {
    const { bars } = stackedBars(days, { width: 300, height: 100, gap: 2 });
    for (let i = 1; i < bars.length; i++) {
      expect(bars[i].x).toBeGreaterThanOrEqual(bars[i - 1].x + bars[i - 1].w + 2);
    }
  });
});
