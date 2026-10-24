from uuid import UUID

from sqlalchemy import delete, insert, text
from sqlalchemy.orm import Session

from app.db.models import Chunk
from app.domain.types import RetrievedChunk, TextChunk

# Build an OR-query from the question's own lexemes. websearch/plainto_tsquery would AND every word,
# so "how long do refunds take" would need "long" AND "take" in the chunk and usually match nothing.
# Each lexeme is quote_literal()'d, so user input can never inject tsquery operators.
KEYWORD_SQL = text(
    """
    WITH q AS (
        SELECT to_tsquery('english', string_agg(quote_literal(lexeme), ' | ')) AS query
        FROM unnest(to_tsvector('english', :q))
    )
    SELECT c.id::text, ts_rank_cd(c.tsv, q.query) AS score
    FROM chunks c, q
    WHERE q.query IS NOT NULL AND c.bot_id = :bot_id AND c.tsv @@ q.query
    ORDER BY score DESC
    LIMIT :k
    """
)

GET_MANY_SQL = text(
    """
    SELECT c.id::text, c.document_id::text, d.title, d.source_url, c.heading, c.content, c.meta
    FROM chunks c JOIN documents d ON d.id = c.document_id
    WHERE c.bot_id = :bot_id AND c.id = ANY(CAST(:ids AS uuid[]))
    """
)


class ChunkRepository:
    def __init__(self, db: Session):
        self.db = db

    def replace_for_document(self, bot_id: UUID, document_id: UUID, chunks: list[TextChunk]) -> list[str]:
        """Delete the document's chunks and bulk-insert the new ones in a single round trip."""
        self.db.execute(delete(Chunk).where(Chunk.document_id == document_id))
        if not chunks:
            return []
        rows = [
            {"bot_id": bot_id, "document_id": document_id, "ordinal": i,
             "heading": c.heading, "content": c.content, "meta": c.meta}
            for i, c in enumerate(chunks)
        ]
        result = self.db.execute(insert(Chunk).returning(Chunk.id, sort_by_parameter_order=True), rows)
        return [str(r[0]) for r in result]

    def keyword_search(self, bot_id: UUID, query: str, k: int) -> list[tuple[str, float]]:
        if not query.strip():
            return []
        rows = self.db.execute(KEYWORD_SQL, {"q": query[:1000], "bot_id": bot_id, "k": k}).all()
        return [(r[0], float(r[1])) for r in rows]

    def get_many(self, bot_id: UUID, chunk_ids: list[str]) -> dict[str, RetrievedChunk]:
        """Hydrate many ids in one query. Filtered by bot_id: another tenant's ids return nothing."""
        if not chunk_ids:
            return {}
        rows = self.db.execute(GET_MANY_SQL, {"bot_id": bot_id, "ids": chunk_ids}).all()
        return {
            r[0]: RetrievedChunk(
                chunk_id=r[0], document_id=r[1], document_title=r[2], source_url=r[3],
                heading=r[4], content=r[5], meta=r[6] or {}, score=0.0,
            )
            for r in rows
        }
