import type { Components } from "react-markdown";
import type { Source } from "./types";
import { safeHref } from "./url";

export function sourceLabel(s: Source) {
  return [s.title, s.heading?.split(" > ").pop(), s.page ? `p. ${s.page}` : null].filter(Boolean).join(" · ");
}

/**
 * Renderers for assistant answers. Answers are LLM output shaped by crawled documents, so they're
 * treated as untrusted: raw HTML is never parsed (no rehype-raw), links must pass safeHref, and
 * images are dropped (no tracking pixels).
 */
export function markdownComponents(byIndex: Map<number, Source>): Components {
  return {
    a: ({ href, children }) => {
      const n = href?.startsWith("#cite-") ? Number(href.slice(6)) : NaN;
      const src = byIndex.get(n);
      if (src) return <CitationChip source={src} />;
      const safe = safeHref(href);
      if (!safe) return <span>{children}</span>;
      return (
        <a href={safe} target="_blank" rel="noopener noreferrer nofollow" className="text-accent underline">
          {children}
        </a>
      );
    },
    img: () => null,
  };
}

function CitationChip({ source }: { source: Source }) {
  return (
    <span className="group relative inline-block align-baseline">
      <button
        type="button"
        aria-label={`Source ${source.index}: ${sourceLabel(source)}`}
        className="mx-0.5 rounded bg-accent/15 px-1 text-[0.7rem] font-semibold text-accent"
      >
        {source.index}
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden w-72 -translate-x-1/2 rounded-lg border border-line bg-surface p-3 text-left text-xs text-ink-2 shadow-lg group-focus-within:block group-hover:block"
      >
        <span className="mb-1 block font-semibold text-ink">{sourceLabel(source)}</span>
        <span className="line-clamp-6 block">{source.snippet}</span>
      </span>
    </span>
  );
}
