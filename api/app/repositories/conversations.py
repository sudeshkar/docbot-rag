from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Conversation, Message


class ConversationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, bot_id: UUID, conversation_id: UUID | None, channel: str) -> Conversation:
        """A client-supplied conversation id is only honoured if it belongs to this bot; otherwise a
        fresh conversation starts, so nobody can read or extend another bot's thread."""
        if conversation_id:
            conv = self.db.scalar(
                select(Conversation).where(Conversation.id == conversation_id, Conversation.bot_id == bot_id)
            )
            if conv:
                return conv
        conv = Conversation(bot_id=bot_id, channel=channel)
        self.db.add(conv)
        self.db.flush()
        return conv

    def recent_messages(self, conversation_id: UUID, limit: int) -> list[dict]:
        """Last `limit` messages oldest-first. LIMIT runs in SQL, so long threads cost the same."""
        rows = self.db.execute(
            select(Message.role, Message.content)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.seq.desc())
            .limit(limit)
        ).all()
        return [{"role": r.role, "content": r.content} for r in reversed(rows)]

    def add_turn(self, conversation_id: UUID, question: str, answer: str, sources: list) -> Message:
        user = Message(conversation_id=conversation_id, role="user", content=question)
        assistant = Message(conversation_id=conversation_id, role="assistant", content=answer, sources=sources)
        self.db.add(user)
        self.db.flush()  # user message gets the lower seq
        self.db.add(assistant)
        self.db.flush()
        return assistant
