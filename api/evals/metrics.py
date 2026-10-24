def recall_at_k(runs: list[list[bool]], k: int) -> float:
    """Fraction of queries with at least one relevant result in the top k (hit rate@k)."""
    if not runs:
        return 0.0
    return sum(any(r[:k]) for r in runs) / len(runs)


def mean_reciprocal_rank(runs: list[list[bool]]) -> float:
    """Average of 1/rank of the first relevant result (0 when none is relevant)."""
    if not runs:
        return 0.0
    total = 0.0
    for r in runs:
        total += next((1.0 / i for i, rel in enumerate(r, start=1) if rel), 0.0)
    return total / len(runs)
