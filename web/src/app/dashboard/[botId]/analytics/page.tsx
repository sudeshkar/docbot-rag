"use client";

import { useEffect, useState } from "react";
import QueriesChart from "@/components/QueriesChart";
import { Card, ErrorText } from "@/components/ui";
import { api } from "@/lib/api";
import { formatCompact, formatMs, formatPercent } from "@/lib/format";
import type { Analytics } from "@/lib/types";
import { useBot } from "../BotContext";

const RANGES = [7, 30, 90];

export default function AnalyticsPage() {
  const { bot } = useBot();
  const [days, setDays] = useState(30);
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.analytics(bot.id, days).then(setData).catch((e) => setError(e.message));
  }, [bot.id, days]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="font-medium">Last {days} days</h2>
        <div className="flex rounded-lg border border-line p-0.5 text-sm" role="group" aria-label="Date range">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setDays(r)}
              aria-pressed={days === r}
              className={`rounded-md px-3 py-1 ${days === r ? "bg-surface-3 font-medium" : "text-ink-2"}`}
            >
              {r}d
            </button>
          ))}
        </div>
      </div>
      <ErrorText>{error}</ErrorText>

      {data && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Stat label="Questions" value={formatCompact(data.total_queries)} />
            <Stat label="Answered from docs" value={formatPercent(data.answer_rate)} />
            <Stat label="Avg response time" value={formatMs(data.avg_latency_ms)} />
            <Stat label="Tokens used" value={formatCompact(data.total_tokens)} />
          </div>

          <Card>
            <h3 className="mb-4 text-sm font-medium">Questions per day</h3>
            <QueriesChart daily={data.daily} />
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <h3 className="text-sm font-medium">Questions your docs couldn&apos;t answer</h3>
              <p className="mb-3 text-xs text-ink-3">Grouped by wording. Write docs for these next.</p>
              {data.unanswered.length === 0 ? (
                <p className="text-sm text-ink-3">Nothing yet.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {data.unanswered.map((q) => (
                    <li key={q.question} className="flex justify-between gap-3 py-2 text-sm">
                      <span className="min-w-0 break-words">{q.question}</span>
                      <span className="shrink-0 tabular-nums text-ink-2">×{q.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card>
              <h3 className="text-sm font-medium">Most cited documents</h3>
              <p className="mb-3 text-xs text-ink-3">Which sources actually power answers.</p>
              {data.top_documents.length === 0 ? (
                <p className="text-sm text-ink-3">Nothing yet.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {data.top_documents.map((d) => (
                    <li key={d.document_id} className="flex justify-between gap-3 py-2 text-sm">
                      <span className="min-w-0 truncate">{d.title ?? "Deleted document"}</span>
                      <span className="shrink-0 tabular-nums text-ink-2">{d.citations}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-4">
      <p className="text-xs text-ink-2">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
    </Card>
  );
}
