import type { Analytics, Bot, ChunkingStrategy, Doc } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Must match CSRF_HEADER in api/app/core/security.py. Cross-site forms can't set custom headers. */
export const CSRF_HEADER = "X-DocBot-CSRF";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set(CSRF_HEADER, "1");
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  // The session is an httpOnly cookie: the browser attaches it, and no script can read it.
  const res = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: "include" });
  // An expired session sends you to login; a wrong password on the login form must not.
  if (res.status === 401 && !path.startsWith("/auth/") && typeof window !== "undefined") {
    window.location.href = "/login";
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

type User = { id: string; email: string };

export const api = {
  signup: (email: string, password: string) =>
    request<User>("/auth/signup", { method: "POST", body: json({ email, password }) }),
  login: (email: string, password: string) =>
    request<User>("/auth/login", { method: "POST", body: json({ email, password }) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<User>("/auth/me"),

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
  // The public widget runs on customers' sites and must never carry the dashboard session.
  const isPublic = path.startsWith("/public/");
  if (!isPublic) headers[CSRF_HEADER] = "1";
  return fetch(`${API_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
    credentials: isPublic ? "omit" : "include",
  });
}
