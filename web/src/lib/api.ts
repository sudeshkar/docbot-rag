import { clearToken, getToken } from "./auth";
import type { Analytics, Bot, ChunkingStrategy, Doc } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (res.status === 401 && token) {
    clearToken();
    if (typeof window !== "undefined") window.location.href = "/login";
  }
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === "string" ? body.detail : body.detail?.[0]?.msg ?? message;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, message);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  signup: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/signup", { method: "POST", body: json({ email, password }) }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", { method: "POST", body: json({ email, password }) }),
  me: () => request<{ id: string; email: string }>("/auth/me"),

  strategies: () => request<ChunkingStrategy[]>("/meta/chunking-strategies"),
  listBots: () => request<Bot[]>("/bots"),
  createBot: (name: string) => request<Bot>("/bots", { method: "POST", body: json({ name }) }),
  getBot: (id: string) => request<Bot>(`/bots/${id}`),
  updateBot: (id: string, patch: Partial<Bot>) =>
    request<Bot>(`/bots/${id}`, { method: "PATCH", body: json(patch) }),
  rotateKey: (id: string) => request<Bot>(`/bots/${id}/rotate-key`, { method: "POST" }),
  deleteBot: (id: string) => request<void>(`/bots/${id}`, { method: "DELETE" }),

  listDocs: (botId: string) => request<Doc[]>(`/bots/${botId}/documents`),
  uploadDoc: (botId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Doc>(`/bots/${botId}/documents/upload`, { method: "POST", body: form });
  },
  addUrl: (botId: string, url: string, crawl: boolean, maxPages?: number) =>
    request<unknown>(`/bots/${botId}/documents/url`, {
      method: "POST",
      body: json({ url, crawl, max_pages: maxPages }),
    }),
  reindexDoc: (botId: string, docId: string) =>
    request<Doc>(`/bots/${botId}/documents/${docId}/reindex`, { method: "POST" }),
  deleteDoc: (botId: string, docId: string) =>
    request<void>(`/bots/${botId}/documents/${docId}`, { method: "DELETE" }),

  analytics: (botId: string, days: number) => request<Analytics>(`/bots/${botId}/analytics?days=${days}`),
};

/** Start a streaming chat request; the caller reads the SSE body. */
export function chatStream(
  path: string,
  body: { question: string; conversation_id?: string | null },
  extraHeaders: Record<string, string> = {},
  signal?: AbortSignal,
): Promise<Response> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...extraHeaders };
  const token = getToken();
  if (token && !path.startsWith("/public/")) headers.Authorization = `Bearer ${token}`;
  return fetch(`${API_URL}${path}`, { method: "POST", headers, body: JSON.stringify(body), signal });
}
