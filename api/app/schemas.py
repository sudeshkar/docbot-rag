from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

from app.rag.chunking.factory import CHUNKERS


def normalize_origin(value: str) -> str:
    """'https://Acme.com/path' -> 'https://acme.com'. Raises ValueError if it isn't an http(s) origin."""
    parts = urlsplit(value.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"Not a valid origin: {value}")
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{parts.hostname.lower()}{port}"


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str


class BotCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class BotUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    instructions: str | None = Field(default=None, max_length=4000)
    welcome_message: str | None = Field(default=None, max_length=300)
    allowed_origins: list[str] | None = Field(default=None, max_length=50)
    monthly_quota: int | None = Field(default=None, ge=0, le=1_000_000)
    chunking_strategy: str | None = None

    @field_validator("allowed_origins")
    @classmethod
    def _origins(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else sorted({normalize_origin(o) for o in v if o.strip()})

    @field_validator("chunking_strategy")
    @classmethod
    def _strategy(cls, v: str | None) -> str | None:
        if v is not None and v not in CHUNKERS:
            raise ValueError(f"Unknown chunking strategy. Options: {sorted(CHUNKERS)}")
        return v


class BotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    public_key: str
    instructions: str
    welcome_message: str
    allowed_origins: list[str]
    monthly_quota: int
    chunking_strategy: str
    created_at: datetime


class BotSummaryOut(BotOut):
    document_count: int = 0
    queries_this_month: int = 0


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    source_type: str
    source_url: str | None
    status: str
    error: str | None
    chunk_count: int
    created_at: datetime


class UrlIngest(BaseModel):
    url: HttpUrl
    crawl: bool = False
    max_pages: int | None = Field(default=None, ge=1, le=100)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None


class PublicBotOut(BaseModel):
    name: str
    welcome_message: str


class ChunkingStrategyOut(BaseModel):
    name: str
    description: str
