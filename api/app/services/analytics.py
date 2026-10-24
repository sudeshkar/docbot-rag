from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

TOTALS_SQL = text(
    """
    SELECT count(*), avg(answered::int), avg(latency_ms), coalesce(sum(input_tokens + output_tokens), 0)
    FROM query_logs
    WHERE bot_id = :bot_id AND created_at >= now() - make_interval(days => :days)
    """
)

# generate_series fills days with no traffic so the chart has no gaps.
DAILY_SQL = text(
    """
    SELECT d::date AS day,
           count(q.id) AS queries,
           count(q.id) FILTER (WHERE q.answered) AS answered
    FROM generate_series(
             date_trunc('day', now() AT TIME ZONE 'UTC') - make_interval(days => :days - 1),
             date_trunc('day', now() AT TIME ZONE 'UTC'),
             interval '1 day') AS d
    LEFT JOIN query_logs q
           ON q.bot_id = :bot_id AND date_trunc('day', q.created_at AT TIME ZONE 'UTC') = d
    GROUP BY d ORDER BY d
    """
)

# Normalize case, whitespace and trailing punctuation so the same question asked differently
# ("Mobile app?" / "mobile app") groups together.
UNANSWERED_SQL = text(
    """
    SELECT lower(regexp_replace(regexp_replace(trim(question), '\\s+', ' ', 'g'), '[[:punct:][:space:]]+$', ''))
               AS question,
           count(*) AS n
    FROM query_logs
    WHERE bot_id = :bot_id AND NOT answered AND created_at >= now() - make_interval(days => :days)
    GROUP BY 1 ORDER BY n DESC, question LIMIT :limit
    """
)

TOP_DOCS_SQL = text(
    """
    SELECT cited.doc_id, d.title, count(*) AS n
    FROM query_logs q
    CROSS JOIN LATERAL jsonb_array_elements_text(q.cited_document_ids) AS cited(doc_id)
    LEFT JOIN documents d ON d.id::text = cited.doc_id AND d.bot_id = q.bot_id
    WHERE q.bot_id = :bot_id AND q.created_at >= now() - make_interval(days => :days)
    GROUP BY cited.doc_id, d.title ORDER BY n DESC LIMIT :limit
    """
)


class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db

    def overview(self, bot_id: UUID, days: int = 30, limit: int = 20) -> dict:
        params = {"bot_id": bot_id, "days": days, "limit": limit}
        total, answer_rate, avg_latency, tokens = self.db.execute(TOTALS_SQL, params).one()
        return {
            "days": days,
            "total_queries": total,
            "answer_rate": float(answer_rate) if answer_rate is not None else None,
            "avg_latency_ms": round(avg_latency) if avg_latency is not None else None,
            "total_tokens": int(tokens),
            "daily": [
                {"day": r.day.isoformat(), "queries": r.queries, "answered": r.answered}
                for r in self.db.execute(DAILY_SQL, params)
            ],
            "unanswered": [
                {"question": r.question, "count": r.n} for r in self.db.execute(UNANSWERED_SQL, params)
            ],
            "top_documents": [
                {"document_id": r.doc_id, "title": r.title, "citations": r.n}
                for r in self.db.execute(TOP_DOCS_SQL, params)
            ],
        }
