"""Compare chunking strategies x retrieval modes on a golden question set.

    python -m evals.run_eval                       # offline, hash embeddings
    python -m evals.run_eval --embedder voyage     # real embeddings (needs VOYAGE_API_KEY)

A retrieved chunk counts as relevant if it contains the golden answer span. Writes a markdown
table to evals/results/latest.md.
"""

import argparse
import json
import time
from pathlib import Path

from app.core.config import get_settings
from app.domain.types import ScoredId
from app.ingest.loaders.registry import load_file
from app.ingest.pipeline import contextual_text, dedupe
from app.rag.chunking.factory import CHUNKERS, create_chunker
from app.rag.embeddings.factory import create_embedder
from app.rag.retrieval.fusion import ReciprocalRankFusion
from evals.indexes import BM25Index, VectorIndex
from evals.metrics import mean_reciprocal_rank, recall_at_k

EVAL_DIR = Path(__file__).parent
ROOT = EVAL_DIR.parents[1]
MODES = ("vector", "keyword", "hybrid")
K = 5


def load_golden(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate(strategy: str, docs_dir: Path, golden: list[dict], embedder) -> dict:
    settings = get_settings()
    chunker = create_chunker(strategy, settings.chunk_tokens, settings.chunk_overlap, embedder)
    chunks = {}
    for path in sorted(docs_dir.glob("*")):
        if path.suffix.lower() not in {".md", ".txt", ".pdf"}:
            continue
        doc = load_file(path, path.name)
        for i, c in enumerate(dedupe(chunker.chunk(doc.sections))):
            chunks[f"{path.name}#{i}"] = (doc.title, c)

    ids = list(chunks)
    vectors = embedder.embed_documents([contextual_text(t, c) for t, c in chunks.values()])
    vindex, bm25 = VectorIndex(), BM25Index()
    for cid, vec, (_, c) in zip(ids, vectors, chunks.values()):
        vindex.add(cid, vec)
        bm25.add(cid, f"{c.heading or ''} {c.content}")

    fusion = ReciprocalRankFusion()
    runs = {m: [] for m in MODES}
    for g in golden:
        vec_hits = [ScoredId(c, s) for c, s in vindex.search(embedder.embed_query(g["question"]), 20)]
        kw_hits = [ScoredId(c, s) for c, s in bm25.search(g["question"], 20)]
        ranked = {
            "vector": [h.chunk_id for h in vec_hits[:K]],
            "keyword": [h.chunk_id for h in kw_hits[:K]],
            "hybrid": [h.chunk_id for h in fusion.fuse([vec_hits, kw_hits], K)],
        }
        needle = g["answer_contains"].lower()
        for mode in MODES:
            runs[mode].append([needle in chunks[cid][1].content.lower() for cid in ranked[mode]])

    sizes = [len(c.content.split()) for _, c in chunks.values()]
    return {
        "strategy": strategy,
        "chunks": len(chunks),
        "avg_words": round(sum(sizes) / len(sizes)) if sizes else 0,
        **{f"{m}_r1": recall_at_k(runs[m], 1) for m in MODES},
        **{f"{m}_r5": recall_at_k(runs[m], 5) for m in MODES},
        **{f"{m}_mrr": mean_reciprocal_rank(runs[m]) for m in MODES},
    }


def to_markdown(rows: list[dict], embedder_name: str, n_questions: int) -> str:
    lines = [
        f"# Retrieval eval: {n_questions} questions, embeddings = `{embedder_name}`, k = {K}",
        "",
        "| Chunking | Chunks | Avg words | Vector R@1 | Vector R@5 | Keyword R@1 | Keyword R@5 | "
        "**Hybrid R@1** | **Hybrid R@5** | Hybrid MRR |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['strategy']} | {r['chunks']} | {r['avg_words']} | {r['vector_r1']:.2f} | {r['vector_r5']:.2f} | "
            f"{r['keyword_r1']:.2f} | {r['keyword_r5']:.2f} | **{r['hybrid_r1']:.2f}** | "
            f"**{r['hybrid_r5']:.2f}** | {r['hybrid_mrr']:.2f} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--docs", type=Path, default=ROOT / "sample_docs")
    parser.add_argument("--golden", type=Path, default=EVAL_DIR / "golden.jsonl")
    parser.add_argument("--embedder", default="hash", choices=["hash", "voyage"])
    parser.add_argument("--strategies", nargs="*", default=sorted(CHUNKERS))
    args = parser.parse_args()

    settings = get_settings()
    embedder = create_embedder(args.embedder, settings.voyage_api_key, settings.voyage_model)
    golden = load_golden(args.golden)

    rows = []
    for strategy in args.strategies:
        started = time.perf_counter()
        rows.append(evaluate(strategy, args.docs, golden, embedder))
        print(f"{strategy:<10} done in {time.perf_counter() - started:.1f}s")

    report = to_markdown(rows, args.embedder, len(golden))
    out = EVAL_DIR / "results" / "latest.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print("\n" + report)


if __name__ == "__main__":
    main()
