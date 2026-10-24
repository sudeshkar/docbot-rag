/** Turn "[n]" markers that match a cited source into markdown links the renderer shows as chips. */
export function linkCitations(text: string, cited: number[]): string {
  const known = new Set(cited);
  return text.replace(/\[(\d{1,3})\](?!\()/g, (match, n: string) =>
    known.has(Number(n)) ? `[${n}](#cite-${n})` : match,
  );
}
