"""Unauthenticated endpoints the embeddable widget calls, identified by the bot's public key.

The key is public by design (it ships in customers' HTML), so cost is protected by per-IP rate
limits, the monthly quota, and an optional origin allowlist.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.container import get_chat_service, get_rate_limiter
from app.core.config import get_settings
from app.db.models import Bot
from app.db.session import get_db
from app.repositories.bots import BotRepository
from app.routers.deps import client_ip
from app.schemas import ChatRequest, PublicBotOut, normalize_origin
from app.services.chat import ChatService
from app.services.rate_limit import RateLimiter

router = APIRouter(prefix="/public/bots", tags=["public"])


def public_bot(public_key: str, db: Session = Depends(get_db)) -> Bot:
    bot = BotRepository(db).get_by_public_key(public_key[:64])
    if bot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown widget key")
    return bot


def check_origin(bot: Bot, embed_origin: str | None) -> None:
    if not bot.allowed_origins:
        return
    try:
        origin = normalize_origin(embed_origin or "")
    except ValueError:
        origin = None
    if origin not in set(bot.allowed_origins):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This widget is not enabled for this website")


@router.get("/{public_key}", response_model=PublicBotOut)
def get_public_bot(bot: Bot = Depends(public_bot)):
    return bot


@router.post("/{public_key}/chat")
def widget_chat(
    body: ChatRequest,
    request: Request,
    bot: Bot = Depends(public_bot),
    x_embed_origin: str | None = Header(default=None),
    limiter: RateLimiter = Depends(get_rate_limiter),
    chat: ChatService = Depends(get_chat_service),
):
    check_origin(bot, x_embed_origin)
    if not limiter.hit(f"widget:{bot.id}:{client_ip(request)}", get_settings().widget_rate_limit_per_min, 60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "You're sending messages too quickly")
    return StreamingResponse(
        chat.chat_turn(bot, body.question, body.conversation_id, "widget"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
