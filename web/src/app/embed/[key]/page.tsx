"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import { API_URL } from "@/lib/api";

type PublicBot = { name: string; welcome_message: string };

function embeddingOrigin(): string | null {
  if (typeof window === "undefined" || window.parent === window) return null;
  return window.location.ancestorOrigins?.[0] ?? null;
}

function EmbedChat() {
  const { key } = useParams<{ key: string }>();
  const claimed = useSearchParams().get("origin") ?? "";
  // Prefer the browser's own record of who framed us; ?origin= is only a fallback for browsers
  // without ancestorOrigins (Firefox), where the frame-ancestors CSP still stops other sites.
  const origin = embeddingOrigin() ?? claimed;
  const [bot, setBot] = useState<PublicBot | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/public/bots/${encodeURIComponent(key)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("This chat is unavailable."))))
      .then(setBot)
      .catch((e) => setError(e.message));
  }, [key]);

  const close = () => window.parent?.postMessage({ type: "docbot:close" }, "*");

  if (error) return <p className="p-4 text-sm text-ink-2">{error}</p>;
  if (!bot) return null;
  return (
    <div className="flex h-dvh flex-col bg-surface">
      <header className="flex items-center justify-between border-b border-line px-4 py-3">
        <span className="font-medium">{bot.name}</span>
        <button onClick={close} aria-label="Close chat" className="rounded p-1 text-ink-2 hover:bg-surface-2">✕</button>
      </header>
      <div className="min-h-0 flex-1">
        <ChatPanel
          endpoint={`/public/bots/${encodeURIComponent(key)}/chat`}
          welcome={bot.welcome_message}
          headers={origin ? { "X-Embed-Origin": origin } : {}}
        />
      </div>
      <p className="py-1.5 text-center text-[10px] text-ink-3">Answers are generated from this site&apos;s documentation.</p>
    </div>
  );
}

export default function EmbedPage() {
  return (
    <Suspense>
      <EmbedChat />
    </Suspense>
  );
}
