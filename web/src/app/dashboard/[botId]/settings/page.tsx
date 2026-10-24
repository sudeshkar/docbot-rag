"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Button, Card, ErrorText, Field, Input, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import type { ChunkingStrategy } from "@/lib/types";
import { useBot } from "../BotContext";

export default function SettingsPage() {
  const { bot, setBot } = useBot();
  const router = useRouter();
  const [form, setForm] = useState({
    name: bot.name,
    instructions: bot.instructions,
    welcome_message: bot.welcome_message,
    monthly_quota: bot.monthly_quota,
    chunking_strategy: bot.chunking_strategy,
  });
  const [strategies, setStrategies] = useState<ChunkingStrategy[]>([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => { api.strategies().then(setStrategies).catch(() => {}); }, []);

  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm((f) => ({ ...f, [k]: v }));
  const strategyChanged = form.chunking_strategy !== bot.chunking_strategy;

  async function save(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      setBot(await api.updateBot(bot.id, form));
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete "${bot.name}" and all its documents? This can't be undone.`)) return;
    try {
      await api.deleteBot(bot.id);
      router.push("/dashboard");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <form onSubmit={save} className="space-y-4">
          <Field label="Name">
            <Input value={form.name} maxLength={120} onChange={(e) => set("name", e.target.value)} />
          </Field>
          <Field label="Welcome message">
            <Input value={form.welcome_message} maxLength={300} onChange={(e) => set("welcome_message", e.target.value)} />
          </Field>
          <Field label="Extra instructions" hint="Tone, language, or what to say when an answer isn't in the docs.">
            <Textarea rows={4} maxLength={4000} value={form.instructions} onChange={(e) => set("instructions", e.target.value)} />
          </Field>
          <Field label="Chunking strategy" hint={strategyChanged ? "Re-index your documents (Sources tab) to apply the new strategy." : undefined}>
            <select
              value={form.chunking_strategy}
              onChange={(e) => set("chunking_strategy", e.target.value)}
              className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm"
            >
              {strategies.map((s) => (
                <option key={s.name} value={s.name}>{s.name}: {s.description}</option>
              ))}
            </select>
          </Field>
          <Field label="Monthly question limit">
            <Input type="number" min={0} max={1000000} value={form.monthly_quota}
              onChange={(e) => set("monthly_quota", Number(e.target.value))} />
          </Field>
          <ErrorText>{error}</ErrorText>
          <div className="flex items-center gap-3">
            <Button>Save changes</Button>
            {saved && <span className="text-sm text-good">Saved</span>}
          </div>
        </form>
      </Card>

      <Card className="border-danger/40">
        <h2 className="font-medium">Delete bot</h2>
        <p className="mb-3 text-sm text-ink-2">Removes the bot, its documents, vectors and analytics.</p>
        <Button variant="danger" onClick={remove}>Delete bot</Button>
      </Card>
    </div>
  );
}
