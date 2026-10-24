"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { ErrorText } from "@/components/ui";
import { api } from "@/lib/api";
import type { Bot } from "@/lib/types";
import { useRequireAuth } from "@/lib/useAuth";
import { BotContext } from "./BotContext";

const tabs = [
  ["", "Sources"],
  ["/playground", "Playground"],
  ["/analytics", "Analytics"],
  ["/embed", "Embed"],
  ["/settings", "Settings"],
] as const;

export default function BotLayout({ children }: { children: ReactNode }) {
  const ready = useRequireAuth();
  const { botId } = useParams<{ botId: string }>();
  const pathname = usePathname();
  const [bot, setBot] = useState<Bot | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (ready) api.getBot(botId).then(setBot).catch((e) => setError(e.message));
  }, [ready, botId]);

  if (!ready) return null;
  const base = `/dashboard/${botId}`;
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-6 sm:px-6">
      <header className="mb-6">
        <Link href="/dashboard" className="text-sm text-ink-2 hover:text-ink">← All bots</Link>
        <h1 className="mt-2 text-2xl font-semibold">{bot?.name ?? " "}</h1>
      </header>
      <nav className="mb-6 flex gap-1 overflow-x-auto overflow-y-hidden border-b border-line" aria-label="Bot sections">
        {tabs.map(([path, label]) => {
          const href = base + path;
          const active = pathname === href;
          return (
            <Link
              key={label}
              href={href}
              aria-current={active ? "page" : undefined}
              className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm ${
                active ? "border-accent font-medium text-ink" : "border-transparent text-ink-2 hover:text-ink"
              }`}
            >
              {label}
            </Link>
          );
        })}
      </nav>
      <ErrorText>{error}</ErrorText>
      {bot && <BotContext.Provider value={{ bot, setBot }}>{children}</BotContext.Provider>}
    </main>
  );
}
