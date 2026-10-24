const DASH = "—";

export function formatPercent(v: number | null | undefined): string {
  return v == null ? DASH : `${Math.round(v * 100)}%`;
}

export function formatMs(v: number | null | undefined): string {
  if (v == null) return DASH;
  return v < 1000 ? `${Math.round(v)} ms` : `${(v / 1000).toFixed(1)} s`;
}

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });

export function formatCompact(v: number): string {
  return compact.format(v);
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
