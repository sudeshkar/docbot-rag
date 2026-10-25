const ALLOWED_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

/**
 * Return a normalized href only for absolute http(s)/mailto URLs, else undefined.
 * The prefix check runs on the raw string so tricks the URL parser would forgive
 * (" javascript:", "java\tscript:") are refused, as are relative and protocol-relative URLs.
 */
export function safeHref(url: string | null | undefined): string | undefined {
  if (!url || !/^(https?:\/\/|mailto:)/i.test(url)) return undefined;
  try {
    const parsed = new URL(url);
    return ALLOWED_PROTOCOLS.has(parsed.protocol) ? parsed.href : undefined;
  } catch {
    return undefined;
  }
}
