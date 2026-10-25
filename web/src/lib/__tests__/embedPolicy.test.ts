import { describe, expect, it, vi } from "vitest";
import { createFrameAncestorsResolver, frameAncestors } from "../embedPolicy";

describe("frameAncestors", () => {
  it("lists exactly the bot's allowed sites", () => {
    expect(frameAncestors(["https://acme.com", "http://localhost:5500"])).toBe(
      "frame-ancestors https://acme.com http://localhost:5500",
    );
  });

  it("allows any site when the bot has no allowlist", () => {
    expect(frameAncestors([])).toBe("frame-ancestors *");
  });

  it("blocks all framing when the bot is unknown or the lookup failed", () => {
    expect(frameAncestors(null)).toBe("frame-ancestors 'none'");
  });

  it("drops anything that isn't a bare http(s) origin, so it can't inject CSP directives", () => {
    expect(
      frameAncestors(["https://ok.com", "https://x.com; script-src *", "*", "javascript:alert(1)", "https://a.com/path"]),
    ).toBe("frame-ancestors https://ok.com");
  });

  it("falls back to 'none' when every entry was invalid, rather than to *", () => {
    expect(frameAncestors(["https://x.com; script-src *"])).toBe("frame-ancestors 'none'");
  });
});

describe("createFrameAncestorsResolver", () => {
  const ok = (origins: string[]) =>
    Promise.resolve(new Response(JSON.stringify({ name: "b", welcome_message: "", allowed_origins: origins })));

  it("fetches the bot's public info and caches it for the TTL", async () => {
    const fetchFn = vi.fn(() => ok(["https://acme.com"]));
    let now = 0;
    const resolve = createFrameAncestorsResolver("http://api:8000", { fetchFn, ttlMs: 60_000, now: () => now });

    expect(await resolve("pk_1")).toBe("frame-ancestors https://acme.com");
    await resolve("pk_1");
    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(fetchFn).toHaveBeenCalledWith("http://api:8000/public/bots/pk_1", expect.anything());

    now = 60_001;
    await resolve("pk_1");
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it("fails closed on 404 and on network errors", async () => {
    const notFound = createFrameAncestorsResolver("http://api", {
      fetchFn: () => Promise.resolve(new Response("{}", { status: 404 })),
    });
    const down = createFrameAncestorsResolver("http://api", { fetchFn: () => Promise.reject(new Error("down")) });
    expect(await notFound("pk_x")).toBe("frame-ancestors 'none'");
    expect(await down("pk_x")).toBe("frame-ancestors 'none'");
  });

  it("url-encodes the key", async () => {
    const fetchFn = vi.fn(() => ok([]));
    await createFrameAncestorsResolver("http://api", { fetchFn })("pk/../../auth/me");
    expect(fetchFn).toHaveBeenCalledWith("http://api/public/bots/pk%2F..%2F..%2Fauth%2Fme", expect.anything());
  });
});
