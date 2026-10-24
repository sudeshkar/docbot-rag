import type { DailyPoint } from "./types";

export type Rect = { y: number; h: number };
export type StackedBar = { day: string; x: number; w: number; answered: Rect; unanswered: Rect; point: DailyPoint };

/** Round up to 1/2/4/5/8 x 10^n so the y-axis top is a readable number. */
export function niceMax(value: number): number {
  if (value <= 0) return 4;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 2, 4, 5, 8, 10]) {
    if (step * magnitude >= value) return step * magnitude;
  }
  return 10 * magnitude;
}

/** Geometry for a two-segment stacked bar chart: answered on the baseline, unanswered on top,
 * separated by a surface-colored gap. Pure, so layout is unit-testable. */
export function stackedBars(
  days: DailyPoint[],
  { width, height, gap }: { width: number; height: number; gap: number },
): { bars: StackedBar[]; max: number } {
  const max = niceMax(Math.max(0, ...days.map((d) => d.queries)));
  const slot = days.length ? width / days.length : width;
  const scale = (n: number) => (n / max) * height;

  const bars = days.map((point, i) => {
    const answeredH = scale(point.answered);
    const unansweredCount = point.queries - point.answered;
    let unansweredH = scale(unansweredCount);
    // Keep a gap between the segments; never let it swallow a non-zero segment entirely.
    if (unansweredCount > 0 && point.answered > 0) unansweredH = Math.max(unansweredH - gap, 1);
    const answeredY = height - answeredH;
    const unansweredY = answeredY - (point.answered > 0 && unansweredCount > 0 ? gap : 0) - unansweredH;
    return {
      day: point.day,
      x: i * slot,
      w: Math.max(slot - gap, 1),
      answered: { y: answeredY, h: answeredH },
      unanswered: { y: unansweredY, h: unansweredH },
      point,
    };
  });
  return { bars, max };
}
