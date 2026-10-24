import re

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
WORDS_PER_TOKEN = 1 / 1.3


def approx_tokens(text: str) -> int:
    # ~1.3 tokens per English word: close enough for budgeting without a tokenizer dependency.
    return int(len(text.split()) * 1.3) + 1


def max_words(tokens: int) -> int:
    return max(1, int(tokens * WORDS_PER_TOKEN))


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in SENTENCE_RE.split(text.strip()) if s.strip()]


def split_by_headings(text: str) -> list[tuple[str | None, str]]:
    """Split markdown on headings. Returns [(heading_path, body)] where heading_path is "A > B > C"."""
    out: list[tuple[str | None, str]] = []
    path: list[tuple[int, str]] = []
    buf: list[str] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body:
            out.append((" > ".join(h for _, h in path) or None, body))
        buf.clear()

    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            path = [(lvl, h) for lvl, h in path if lvl < level] + [(level, m.group(2).strip())]
        else:
            buf.append(line)
    flush()
    return out
