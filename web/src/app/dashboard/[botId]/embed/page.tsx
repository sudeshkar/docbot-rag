"use client";

import { useState } from "react";
import { Button, Card, ErrorText, Field, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useBot } from "../BotContext";

export default function EmbedPage() {
  const { bot, setBot } = useBot();
  const [origins, setOrigins] = useState(bot.allowed_origins.join("\n"));
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const appOrigin = typeof window === "undefined" ? "" : window.location.origin;
  const snippet = `<script src="${appOrigin}/widget.js" data-key="${bot.public_key}" async></script>`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setError("Couldn't copy. Select the snippet and copy it manually.");
    }
  }

  async function saveOrigins() {
    setError("");
    try {
      const list = origins.split(/[\s,]+/).filter(Boolean);
      const updated = await api.updateBot(bot.id, { allowed_origins: list });
      setBot(updated);
      setOrigins(updated.allowed_origins.join("\n"));
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function rotate() {
    if (!window.confirm("Rotate the widget key? Every site using the current snippet will stop working until you update it.")) return;
    try {
      setBot(await api.rotateKey(bot.id));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <h2 className="font-medium">Embed snippet</h2>
        <p className="mb-3 text-sm text-ink-2">Paste this before the closing &lt;/body&gt; tag on any page.</p>
        <pre className="overflow-x-auto rounded-lg bg-surface-2 p-3 font-mono text-xs">{snippet}</pre>
        <div className="mt-3 flex gap-2">
          <Button onClick={copy}>{copied ? "Copied" : "Copy snippet"}</Button>
          <a href={`/embed/${bot.public_key}`} target="_blank" rel="noopener" className="rounded-lg border border-line px-3.5 py-2 text-sm hover:bg-surface-2">
            Preview widget
          </a>
        </div>
      </Card>

      <Card>
        <h2 className="font-medium">Allowed websites</h2>
        <Field label="" hint="One origin per line, like https://acme.com. Leave empty to allow any site. Rate limits and the monthly quota always apply.">
          <Textarea rows={4} value={origins} onChange={(e) => setOrigins(e.target.value)} placeholder="https://acme.com" />
        </Field>
        <div className="mt-3 flex items-center gap-3">
          <Button onClick={saveOrigins}>Save</Button>
          {saved && <span className="text-sm text-good">Saved</span>}
        </div>
      </Card>

      <Card>
        <h2 className="font-medium">Widget key</h2>
        <p className="mb-3 text-sm text-ink-2">
          The key is public by design. Rotate it if it&apos;s being abused somewhere you don&apos;t control.
        </p>
        <code className="mb-3 block break-all font-mono text-xs text-ink-2">{bot.public_key}</code>
        <Button variant="secondary" onClick={rotate}>Rotate key</Button>
      </Card>
      <ErrorText>{error}</ErrorText>
    </div>
  );
}
