import { describe, expect, it } from "vitest";
import { formatCompact, formatMs, formatPercent } from "../format";

describe("format", () => {
  it("formats percentages, latency and large numbers", () => {
    expect(formatPercent(0.8333)).toBe("83%");
    expect(formatPercent(null)).toBe("—");
    expect(formatMs(840)).toBe("840 ms");
    expect(formatMs(2450)).toBe("2.5 s");
    expect(formatMs(null)).toBe("—");
    expect(formatCompact(1234)).toBe("1.2K");
    expect(formatCompact(12)).toBe("12");
  });
});
