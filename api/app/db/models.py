import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Identity,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _uuid()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = _created()

    bots: Mapped[list["Bot"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Bot(Base):
    __tablename__ = "bots"
    id: Mapped[uuid.UUID] = _uuid()
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    public_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    instructions: Mapped[str] = mapped_column(Text, default="")
    welcome_message: Mapped[str] = mapped_column(String(300), default="Hi! Ask me anything about our docs.")
    allowed_origins: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    monthly_quota: Mapped[int] = mapped_column(Integer, default=1000)
    chunking_strategy: Mapped[str] = mapped_column(String(20), default="markdown")
    created_at: Mapped[datetime] = _created()

    owner: Mapped[User] = relationship(back_populates="bots")
    documents: Mapped[list["Document"]] = relationship(back_populates="bot", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = _uuid()
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(20))  # file | url
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|processing|ready|failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _created()

    bot: Mapped[Bot] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    """Chunk text lives here for keyword (FTS) search; its embedding lives in Chroma under the same id."""

    __tablename__ = "chunks"
    id: Mapped[uuid.UUID] = _uuid()
    # Denormalized so every keyword query can filter on the tenant without a join.
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    tsv = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(heading, '') || ' ' || content)", persisted=True),
    )

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = _uuid()
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(20))  # playground | widget
    created_at: Mapped[datetime] = _created()

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.seq"
    )


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = _uuid()
    # now() is fixed for a whole transaction, so timestamps can't order two messages saved together.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), index=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))  # user | assistant
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = _created()

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class QueryLog(Base):
    __tablename__ = "query_logs"
    id: Mapped[uuid.UUID] = _uuid()
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(20))
    question: Mapped[str] = mapped_column(Text)
    top_score: Mapped[float] = mapped_column(Float, default=0.0)
    answered: Mapped[bool] = mapped_column(Boolean, default=True)
    cited_document_ids: Mapped[list] = mapped_column(JSONB, default=list)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _created()

    # Every analytics/quota query is "this bot, since time T": one composite B-tree serves them all.
    __table_args__ = (Index("ix_query_logs_bot_created", "bot_id", "created_at"),)
