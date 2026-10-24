from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, document_id: UUID) -> Document | None:
        return self.db.get(Document, document_id)

    def get_for_bot(self, bot_id: UUID, document_id: UUID) -> Document | None:
        return self.db.scalar(select(Document).where(Document.id == document_id, Document.bot_id == bot_id))

    def list_for_bot(self, bot_id: UUID) -> list[Document]:
        return list(
            self.db.scalars(select(Document).where(Document.bot_id == bot_id).order_by(Document.created_at.desc()))
        )

    def add(self, doc: Document) -> Document:
        self.db.add(doc)
        self.db.flush()
        return doc

    def delete(self, doc: Document) -> None:
        self.db.delete(doc)
        self.db.flush()
