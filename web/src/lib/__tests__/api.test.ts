import { afterEach, describe, expect, it, vi } from "vitest";
import { api, chatStream, CSRF_HEADER } from "../api";

function stubFetch(status = 200, body: unknown = {}) {
  const fetchFn = vi.fn<typeof fetch>(() =>
    Promise.resolve(
      // 204 responses can't have a body
      new Response(status === 204 ? null : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  vi.stubGlobal("fetch", fetchFn);
  return fetchFn;
}

const initOf = (fetchFn: ReturnType<typeof stubFetch>) => fetchFn.mock.calls[0][1] as RequestInit;

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("sends the session cookie and the CSRF header, and never an Authorization header", async () => {
    const fetchFn = stubFetch(201, { id: "b1" });
    await api.createBot("Support");
    const init = initOf(fetchFn);
    const headers = new Headers(init.headers);
    expect(init.credentials).toBe("include");
    expect(headers.get(CSRF_HEADER)).toBe("1");
    expect(headers.has("Authorization")).toBe(false);
  });

  it("logs out through the API, since scripts can't clear an httpOnly cookie", async () => {
    const fetchFn = stubFetch(204);
    await api.logout();
    expect(fetchFn.mock.calls[0][0]).toMatch(/\/auth\/logout$/);
    expect(initOf(fetchFn).method).toBe("POST");
  });

  it("surfaces a failed login as an error instead of redirecting", async () => {
    stubFetch(401, { detail: "Invalid email or password" });
    await expect(api.login("a@b.co", "wrong")).rejects.toThrow("Invalid email or password");
  });
});

describe("chatStream", () => {
  it("sends credentials for the dashboard playground", async () => {
    const fetchFn = stubFetch();
    await chatStream("/bots/b1/chat", { question: "q" });
    const init = initOf(fetchFn);
    expect(init.credentials).toBe("include");
    expect(new Headers(init.headers).get(CSRF_HEADER)).toBe("1");
  });

  it("never sends the dashboard cookie from the public widget", async () => {
    const fetchFn = stubFetch();
    await chatStream("/public/bots/pk_1/chat", { question: "q" });
    expect(initOf(fetchFn).credentials).toBe("omit");
  });
});
