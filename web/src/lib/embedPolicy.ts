/**
 * CSP frame-ancestors for the embeddable chat iframe. The browser enforces it, so a site that
 * isn't on the bot's allowlist can't display the widget at all, whatever ?origin= it claims.
 */

// A bare http(s) origin: no path, spaces, ";" or wildcards, so a stored value can't inject CSP directives.
const ORIGIN = /^https?:\/\/[a-z0-9.-]+(:\d{1,5})?$/i;

/** null = unknown bot or failed lookup (fail closed); [] = no allowlist (any site may embed). */
export function frameAncestors(origins: string[] | null): string {
  if (origins === null) return "frame-ancestors 'none'";
  if (origins.length === 0) return "frame-ancestors *";
  const valid = origins.filter((o) => ORIGIN.test(o));
  return `frame-ancestors ${valid.length ? valid.join(" ") : "'none'"}`;
}

type Options = { fetchFn?: typeof fetch; ttlMs?: number; now?: () => number; maxEntries?: number };

/**
 * Looks up a bot's allowlist from the API and caches the policy per key for ttlMs, so iframe loads
 * don't each cost an API call. O(1) per lookup; the cache is capped and evicts the oldest entry.
 */
export function createFrameAncestorsResolver(apiUrl: string, options: Options = {}) {
  const { fetchFn = fetch, ttlMs = 60_000, now = Date.now, maxEntries = 1000 } = options;
  const cache = new Map<string, { policy: string; expires: number }>();

  return async function resolve(key: string): Promise<string> {
    const hit = cache.get(key);
    if (hit && hit.expires > now()) return hit.policy;

    let origins: string[] | null = null;
    try {
      const res = await fetchFn(`${apiUrl}/public/bots/${encodeURIComponent(key)}`, { cache: "no-store" });
      if (res.ok) {
        const body = (await res.json()) as { allowed_origins?: unknown };
        if (Array.isArray(body.allowed_origins)) origins = body.allowed_origins.filter((o) => typeof o === "string");
      }
    } catch {
      origins = null; // API unreachable: block framing rather than allow everyone
    }

    const policy = frameAncestors(origins);
    if (cache.size >= maxEntries) cache.delete(cache.keys().next().value!); // Map keeps insertion order
    cache.set(key, { policy, expires: now() + ttlMs });
    return policy;
  };
}
