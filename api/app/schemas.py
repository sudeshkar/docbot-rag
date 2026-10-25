import re
import unicodedata
from datetime import datetime
from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, EmailStr, Field, HttpUrl, field_validator

from app.core.security import BCRYPT_MAX_BYTES
from app.rag.chunking.factory import CHUNKERS


# Bidi embeddings/overrides/isolates (text-direction spoofing), zero-width space and BOM (filter evasion).
# ZWNJ/ZWJ (U+200C/D) are kept: emoji sequences and several scripts need them.
_INVISIBLE = dict.fromkeys(
    [*range(0x202A, 0x202F), *range(0x2066, 0x206A), 0x200B, 0xFEFF]
)
# A tag opener as browsers parse it: "<" directly followed by a letter, "/", "!" or "?".
# "a < b" and "<3" stay valid.
_HTML_TAG = re.compile(r"<[A-Za-z/!?]")


def clean_text(value: str, multiline: bool = False) -> str:
    """NFC-normalize, drop control and invisible characters, and trim. O(len(value)).

    Single-line fields turn newlines and tabs into spaces; multi-line fields keep them.
    """
    value = unicodedata.normalize("NFC", value.replace("\r\n", "\n")).translate(_INVISIBLE)
    out = []
    for ch in value:
        if ch in "\n\t":
            out.append(ch if multiline else " ")
        elif unicodedata.category(ch) != "Cc":
            out.append(ch)
    return "".join(out).strip()


def _cleaner(multiline: bool):
    return lambda v: clean_text(v, multiline) if isinstance(v, str) else v


def reject_html(value: str) -> str:
    # React escapes on output, so this is defense in depth: plain-text fields never need markup,
    # and rejecting it keeps stored payloads away from any future non-escaping consumer.
    if _HTML_TAG.search(value):
        raise ValueError("HTML tags are not allowed")
    return value


# Cleaning runs before the length checks, so "   " fails min_length.
SingleLineText = Annotated[str, BeforeValidator(_cleaner(multiline=False)), AfterValidator(reject_html)]
MultiLineText = Annotated[str, BeforeValidator(_cleaner(multiline=True))]


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

    @field_validator("password")
    @classmethod
    def fits_bcrypt(cls, v: str) -> str:
        # Measured in UTF-8 bytes, not characters: accented letters and emoji take 2-4 bytes each.
        if len(v.encode()) > BCRYPT_MAX_BYTES:
            raise ValueError(f"Password must be at most {BCRYPT_MAX_BYTES} bytes")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str


class BotCreate(BaseModel):
    name: SingleLineText = Field(min_length=1, max_length=120)


class BotUpdate(BaseModel):
    name: SingleLineText | None = Field(default=None, min_length=1, max_length=120)
    instructions: MultiLineText | None = Field(default=None, max_length=4000)
    welcome_message: SingleLineText | None = Field(default=None, max_length=300)
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
    # Not reject_html: questions are never rendered as HTML, and asking about "<script> tags" is legitimate.
    question: MultiLineText = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None


class PublicBotOut(BaseModel):
    name: str
    welcome_message: str
    # Public by nature (they're the sites showing the widget); the web app turns them into frame-ancestors.
    allowed_origins: list[str]


class ChunkingStrategyOut(BaseModel):
    name: str
    description: str
