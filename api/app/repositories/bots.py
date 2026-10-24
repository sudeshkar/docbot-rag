from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Bot, Document, QueryLog


def month_start() -> datetime:
    return datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@dataclass
class BotSummary:
    bot: Bot
    document_count: int
    queries_this_month: int


class BotRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, bot_id: UUID) -> Bot | None:
        return self.db.get(Bot, bot_id)

    def get_for_owner(self, owner_id: UUID, bot_id: UUID) -> Bot | None:
        """Ownership is part of the lookup, so a caller can't load a bot by guessing its id."""
        return self.db.scalar(select(Bot).where(Bot.id == bot_id, Bot.owner_id == owner_id))

    def get_by_public_key(self, public_key: str) -> Bot | None:
        return self.db.scalar(select(Bot).where(Bot.public_key == public_key))

    def list_for_owner(self, owner_id: UUID) -> list[BotSummary]:
        """Bots with document and monthly query counts in ONE query (correlated subqueries), not 1 + 2N."""
        docs = (
            select(func.count(Document.id)).where(Document.bot_id == Bot.id).correlate(Bot).scalar_subquery()
        )
        queries = (
            select(func.count(QueryLog.id))
            .where(QueryLog.bot_id == Bot.id, QueryLog.created_at >= month_start())
            .correlate(Bot)
            .scalar_subquery()
        )
        rows = self.db.execute(
            select(Bot, docs, queries).where(Bot.owner_id == owner_id).order_by(Bot.created_at.desc())
        ).all()
        return [BotSummary(bot, d, q) for bot, d, q in rows]

    def add(self, bot: Bot) -> Bot:
        self.db.add(bot)
        self.db.flush()
        return bot

    def delete(self, bot: Bot) -> None:
        self.db.delete(bot)
        self.db.flush()
