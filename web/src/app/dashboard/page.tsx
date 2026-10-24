"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import Logo from "@/components/Logo";
import { Button, Card, ErrorText, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { clearToken } from "@/lib/auth";
import type { Bot } from "@/lib/types";
import { useRequireAuth } from "@/lib/useAuth";

export default function Dashboard() {
  const ready = useRequireAuth();
  const router = useRouter();
  const [bots, setBots] = useState<Bot[] | null>(null);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!ready) return;
    api.listBots().then(setBots).catch((e) => setError(e.message));
    api.me().then((u) => setEmail(u.email)).catch(() => {});
  }, [ready]);

  async function create(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      const bot = await api.createBot(name.trim());
      router.push(`/dashboard/${bot.id}`);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!ready) return null;
  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
      <header className="mb-8 flex items-center justify-between">
        <Logo href="/dashboard" />
        <div className="flex items-center gap-3 text-sm text-ink-2">
          <span className="hidden sm:inline">{email}</span>
          <Button variant="ghost" onClick={() => { clearToken(); router.push("/login"); }}>Log out</Button>
        </div>
      </header>

      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Your bots</h1>
          <p className="text-sm text-ink-2">Each bot has its own documents, widget key and analytics.</p>
        </div>
        <form onSubmit={create} className="flex gap-2">
          <Input placeholder="New bot name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} className="sm:w-56" />
          <Button disabled={!name.trim()}>Create</Button>
        </form>
      </div>

      <ErrorText>{error}</ErrorText>

      {bots === null ? (
        <p className="text-sm text-ink-3">Loading…</p>
      ) : bots.length === 0 ? (
        <Card className="py-12 text-center">
          <p className="font-medium">No bots yet</p>
          <p className="mt-1 text-sm text-ink-2">Create one above, then upload your docs.</p>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {bots.map((b) => (
            <Link key={b.id} href={`/dashboard/${b.id}`} className="rounded-xl border border-line p-5 transition hover:border-accent">
              <p className="font-medium">{b.name}</p>
              <p className="mt-3 text-sm text-ink-2">
                {b.document_count} {b.document_count === 1 ? "document" : "documents"} · {b.queries_this_month} questions this month
              </p>
              <p className="mt-1 text-xs text-ink-3">Chunking: {b.chunking_strategy}</p>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
