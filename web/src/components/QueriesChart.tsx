"use client";

import { useState } from "react";
import { stackedBars } from "@/lib/chart";
import { formatDate } from "@/lib/format";
import type { DailyPoint } from "@/lib/types";

const W = 720;
const H = 200;
const PAD = { top: 8, right: 8, bottom: 24, left: 32 };
const GAP = 2;

/** Bar path with rounded top (data-end) corners and a square baseline. */
function topRounded(x: number, y: number, w: number, h: number, r = 4): string {
  if (h <= 0) return "";
  const rr = Math.min(r, w / 2, h);
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`;
}

export default function QueriesChart({ daily }: { daily: DailyPoint[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const { bars, max } = stackedBars(daily, { width: innerW, height: innerH, gap: GAP });
  const ticks = [0, max / 2, max];
  const labelIdx = new Set([0, Math.floor((daily.length - 1) / 2), daily.length - 1]);
  const active = hover != null ? bars[hover] : null;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-4 text-xs text-ink-2">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: "var(--series-1)" }} /> Answered
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: "var(--series-2)" }} /> Not answered
          </span>
        </div>
        <button onClick={() => setShowTable((v) => !v)} className="text-xs text-ink-2 underline-offset-2 hover:underline">
          {showTable ? "Show chart" : "View as table"}
        </button>
      </div>

      {showTable ? (
        <div className="max-h-64 overflow-auto rounded-lg border border-line">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-surface-2 text-left text-xs text-ink-2">
              <tr><th className="px-3 py-2">Day</th><th className="px-3 py-2 text-right">Queries</th><th className="px-3 py-2 text-right">Answered</th></tr>
            </thead>
            <tbody>
              {daily.map((d) => (
                <tr key={d.day} className="border-t border-line">
                  <td className="px-3 py-1.5">{formatDate(d.day)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{d.queries}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{d.answered}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="relative">
          <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Queries per day, answered versus not answered">
            <g transform={`translate(${PAD.left},${PAD.top})`}>
              {ticks.map((t) => {
                const y = innerH - (t / max) * innerH;
                return (
                  <g key={t}>
                    <line x1={0} x2={innerW} y1={y} y2={y} stroke="var(--line)" strokeWidth={1} />
                    <text x={-8} y={y} dy="0.32em" textAnchor="end" fontSize={11} fill="var(--ink-3)">{t}</text>
                  </g>
                );
              })}
              {bars.map((b, i) => (
                <g key={b.day} opacity={hover == null || hover === i ? 1 : 0.45}>
                  <path d={topRounded(b.x, b.answered.y, b.w, b.answered.h, b.unanswered.h > 0 ? 0 : 4)} fill="var(--series-1)" />
                  <path d={topRounded(b.x, b.unanswered.y, b.w, b.unanswered.h)} fill="var(--series-2)" />
                  {labelIdx.has(i) && (
                    <text x={b.x + b.w / 2} y={innerH + 16} textAnchor="middle" fontSize={11} fill="var(--ink-3)">
                      {formatDate(b.day)}
                    </text>
                  )}
                  {/* full-height hit target, larger than the mark */}
                  <rect
                    x={b.x}
                    y={0}
                    width={b.w + GAP}
                    height={innerH}
                    fill="transparent"
                    onMouseEnter={() => setHover(i)}
                    onMouseLeave={() => setHover(null)}
                  />
                </g>
              ))}
            </g>
          </svg>
          {active && (
            <div
              className="pointer-events-none absolute top-0 z-10 rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-md"
              style={{
                left: `${((PAD.left + active.x + active.w / 2) / W) * 100}%`,
                transform: `translateX(${(active.x / innerW) > 0.7 ? "-100%" : "-50%"})`,
              }}
            >
              <div className="mb-1 font-medium text-ink">{formatDate(active.day)}</div>
              <div className="text-ink-2">Answered: <span className="tabular-nums text-ink">{active.point.answered}</span></div>
              <div className="text-ink-2">Not answered: <span className="tabular-nums text-ink">{active.point.queries - active.point.answered}</span></div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
