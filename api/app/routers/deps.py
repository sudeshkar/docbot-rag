from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Bot, User
from app.db.session import get_db
from app.repositories.bots import BotRepository


def owned_bot(bot_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Bot:
    bot = BotRepository(db).get_for_owner(user.id, bot_id)
    if bot is None:
        # 404 rather than 403: don't confirm that someone else's bot id exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bot not found")
    return bot


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
