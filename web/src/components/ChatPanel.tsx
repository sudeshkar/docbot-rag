"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import { chatStream } from "@/lib/api";
import { linkCitations } from "@/lib/citations";
import { readSSE } from "@/lib/sse";
import type { Source } from "@/lib/types";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  answered?: boolean;
  lowConfidence?: boolean;
  error?: string;
  pending?: boolean;
};

type Props = {
  endpoint: string;
  welcome: string;
  headers?: Record<string, string>;
  showDiagnostics?: boolean;
  suggestions?: string[];
};

export default function ChatPanel({ endpoint, welcome, headers, showDiagnostics, suggestions = [] }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const conversationId = useRef<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => bottom.current?.scrollIntoView({ block: "end" }), [messages]);

  const patchLast = (patch: (m: ChatMessage) => ChatMessage) =>
    setMessages((prev) => [...prev.slice(0, -1), patch(prev[prev.length - 1])]);

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setInput("");
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      { role: "assistant", content: "", pending: true },
    ]);
    abort.current = new AbortController();
    try {
      const res = await chatStream(
        endpoint,
        { question, conversation_id: conversationId.current },
        headers,
        abort.current.signal,
      );
      if (!res.ok || !res.body) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail ?? `Request failed (${res.status})`);
      }
      for await (const { event, data } of readSSE(res.body)) {
        if (event === "meta") conversationId.current = (data as { conversation_id: string }).conversation_id;
        else if (event === "token") patchLast((m) => ({ ...m, content: m.content + (data as string), pending: false }));
        else if (event === "sources") patchLast((m) => ({ ...m, sources: data as Source[] }));
        else if (event === "done") {
          const d = data as { answered: boolean; low_confidence: boolean };
          patchLast((m) => ({ ...m, answered: d.answered, lowConfidence: d.low_confidence, pending: false }));
        } else if (event === "error") {
          patchLast((m) => ({ ...m, error: (data as { message: string }).message, pending: false }));
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        patchLast((m) => ({ ...m, error: (err as Error).message || "Something went wrong", pending: false }));
      }
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    ask(input);
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-4" aria-live="polite">
        <Bubble role="assistant">
          <p>{welcome}</p>
        </Bubble>
        {messages.length === 0 && suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => ask(s)}
                className="rounded-full border border-line px-3 py-1 text-xs text-ink-2 hover:bg-surface-2"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <Bubble key={i} role={m.role}>
            {m.role === "user" ? (
              <p className="whitespace-pre-wrap">{m.content}</p>
            ) : (
              <AssistantBody message={m} showDiagnostics={showDiagnostics} />
            )}
          </Bubble>
        ))}
        <div ref={bottom} />
      </div>
      <form onSubmit={onSubmit} className="flex gap-2 border-t border-line p-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question…"
          maxLength={2000}
          aria-label="Your question"
          className="flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <button
          disabled={busy || !input.trim()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-ink disabled:opacity-50"
        >
          {busy ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}

function Bubble({ role, children }: { role: "user" | "assistant"; children: React.ReactNode }) {
  const mine = role === "user";
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          mine ? "bg-accent text-accent-ink" : "bg-surface-2 text-ink"
        }`}
      >
        {children}
      </div>
    </div>
  );
}

function AssistantBody({ message, showDiagnostics }: { message: ChatMessage; showDiagnostics?: boolean }) {
  const sources = message.sources ?? [];
  const byIndex = new Map(sources.map((s) => [s.index, s]));
  if (message.pending) return <TypingDots />;
  return (
    <div className="space-y-2">
      {message.content && (
        <div className="prose-chat">
          <ReactMarkdown
            components={{
              a: ({ href, children }) => {
                const n = href?.startsWith("#cite-") ? Number(href.slice(6)) : NaN;
                const src = byIndex.get(n);
                if (src) return <CitationChip source={src} />;
                return (
                  <a href={href} target="_blank" rel="noopener noreferrer nofollow" className="text-accent underline">
                    {children}
                  </a>
                );
              },
            }}
          >
            {linkCitations(message.content, [...byIndex.keys()])}
          </ReactMarkdown>
        </div>
      )}
      {message.error && <p className="text-danger">{message.error}</p>}
      {sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-t border-line pt-2">
          {sources.map((s) => (
            <SourceLink key={s.index} source={s} />
          ))}
        </div>
      )}
      {showDiagnostics && message.answered !== undefined && (
        <p className="text-xs text-ink-3">
          {message.answered ? "Grounded answer" : "Not answered from docs: will show in Analytics"}
          {message.lowConfidence ? " · low retrieval confidence" : ""}
        </p>
      )}
    </div>
  );
}

function sourceLabel(s: Source) {
  return [s.title, s.heading?.split(" > ").pop(), s.page ? `p. ${s.page}` : null].filter(Boolean).join(" · ");
}

function CitationChip({ source }: { source: Source }) {
  return (
    <span className="group relative inline-block align-baseline">
      <button
        type="button"
        aria-label={`Source ${source.index}: ${sourceLabel(source)}`}
        className="mx-0.5 rounded bg-accent/15 px-1 text-[0.7rem] font-semibold text-accent"
      >
        {source.index}
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden w-72 -translate-x-1/2 rounded-lg border border-line bg-surface p-3 text-left text-xs text-ink-2 shadow-lg group-focus-within:block group-hover:block"
      >
        <span className="mb-1 block font-semibold text-ink">{sourceLabel(source)}</span>
        <span className="line-clamp-6 block">{source.snippet}</span>
      </span>
    </span>
  );
}

function SourceLink({ source }: { source: Source }) {
  const label = `${source.index}. ${sourceLabel(source)}`;
  const cls = "max-w-full truncate rounded-md border border-line bg-surface px-2 py-0.5 text-xs text-ink-2";
  return source.url ? (
    <a href={source.url} target="_blank" rel="noopener noreferrer nofollow" className={`${cls} hover:text-ink`}>
      {label}
    </a>
  ) : (
    <span className={cls} title={source.snippet}>
      {label}
    </span>
  );
}

function TypingDots() {
  return (
    <span className="flex gap-1 py-1" aria-label="Assistant is typing">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-3"
          style={{ animationDelay: `${i * 120}ms` }}
        />
      ))}
    </span>
  );
}
