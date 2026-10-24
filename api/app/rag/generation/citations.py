import re

CITATION_RE = re.compile(r"\[(\d{1,3})\]")


def extract_citations(answer: str, n_sources: int) -> list[int]:
    """Source indices cited in the answer, in first-cited order. O(len(answer)) with a seen-set."""
    seen: set[int] = set()
    ordered: list[int] = []
    for m in CITATION_RE.finditer(answer):
        idx = int(m.group(1))
        if 1 <= idx <= n_sources and idx not in seen:
            seen.add(idx)
            ordered.append(idx)
    return ordered
