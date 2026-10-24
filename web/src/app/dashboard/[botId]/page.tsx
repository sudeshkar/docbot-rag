"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Button, Card, ErrorText, Input, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Doc } from "@/lib/types";
import { useBot } from "./BotContext";

const POLL_MS = 2000;

export default function SourcesPage() {
  const { bot } = useBot();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [uploading, setUploading] = useState(false);
  const [url, setUrl] = useState("");
  const [crawl, setCrawl] = useState(true);
  const fileInput = useRef<HTMLInputElement>(null);

  const refresh = useCallback(() => api.listDocs(bot.id).then(setDocs).catch((e) => setError(e.message)), [bot.id]);
  useEffect(() => { refresh(); }, [refresh]);

  // Poll only while something is still being ingested.
  const inFlight = docs.some((d) => d.status === "queued" || d.status === "processing");
  useEffect(() => {
    if (!inFlight && !notice) return;
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [inFlight, notice, refresh]);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setError("");
    setUploading(true);
    try {
      for (const f of Array.from(files)) await api.uploadDoc(bot.id, f);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function addUrl(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.addUrl(bot.id, url.trim(), crawl);
      setUrl("");
      setNotice(crawl ? "Crawling started. Pages appear below as they're indexed." : "");
      await refresh();
      if (crawl) setTimeout(() => setNotice(""), 60_000);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove(doc: Doc) {
    await api.deleteDoc(bot.id, doc.id).catch((e) => setError(e.message));
    refresh();
  }

  async function reindex(doc: Doc) {
    await api.reindexDoc(bot.id, doc.id).catch((e) => setError(e.message));
    refresh();
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <h2 className="font-medium">Upload files</h2>
          <p className="mb-4 text-sm text-ink-2">PDF, Markdown or text, up to 20 MB each.</p>
          <label
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); upload(e.dataTransfer.files); }}
            className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-line px-4 py-8 text-center text-sm text-ink-2 hover:border-accent"
          >
            {uploading ? "Uploading…" : "Drop files here or click to browse"}
            <input
              ref={fileInput}
              type="file"
              multiple
              accept=".pdf,.md,.markdown,.txt"
              className="sr-only"
              onChange={(e) => upload(e.target.files)}
            />
          </label>
        </Card>
        <Card>
          <h2 className="font-medium">Add a website</h2>
          <p className="mb-4 text-sm text-ink-2">Index one page, or crawl the whole site (same domain, up to 25 pages).</p>
          <form onSubmit={addUrl} className="space-y-3">
            <Input type="url" required placeholder="https://help.example.com" value={url} onChange={(e) => setUrl(e.target.value)} />
            <label className="flex items-center gap-2 text-sm text-ink-2">
              <input type="checkbox" checked={crawl} onChange={(e) => setCrawl(e.target.checked)} />
              Crawl linked pages
            </label>
            <Button disabled={!url.trim()}>{crawl ? "Start crawl" : "Add page"}</Button>
          </form>
        </Card>
      </div>

      <ErrorText>{error}</ErrorText>
      {notice && <p className="text-sm text-ink-2">{notice}</p>}

      <Card className="p-0">
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <h2 className="font-medium">Documents</h2>
          <span className="text-xs text-ink-3">Chunking: {bot.chunking_strategy}</span>
        </div>
        {docs.length === 0 ? (
          <p className="px-5 py-10 text-center text-sm text-ink-3">No documents yet.</p>
        ) : (
          <ul className="divide-y divide-line">
            {docs.map((d) => (
              <li key={d.id} className="flex flex-col gap-2 px-5 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium" title={d.title}>{d.title}</p>
                  <p className="text-xs text-ink-3">
                    {d.source_type === "url" ? d.source_url : "Uploaded file"} · {formatDate(d.created_at)}
                    {d.status === "ready" && ` · ${d.chunk_count} chunks`}
                  </p>
                  {d.error && <p className="mt-1 text-xs text-danger">{d.error}</p>}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <StatusBadge status={d.status} />
                  <Button variant="ghost" className="px-2 py-1 text-xs" onClick={() => reindex(d)}>Re-index</Button>
                  <Button variant="ghost" className="px-2 py-1 text-xs text-danger" onClick={() => remove(d)}>Delete</Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
