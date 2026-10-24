from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import QueryLog


class QueryLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, log: QueryLog) -> None:
        self.db.add(log)
        self.db.flush()

    def count_since(self, bot_id: UUID, since: datetime) -> int:
        return self.db.scalar(
            select(func.count(QueryLog.id)).where(QueryLog.bot_id == bot_id, QueryLog.created_at >= since)
        ) or 0
