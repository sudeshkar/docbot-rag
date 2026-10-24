from pathlib import Path

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.container import get_chat_service, get_vector_store
from app.core.security import get_current_user, new_public_key
from app.db.models import Bot, User
from app.db.session import get_db
from app.rag.chunking.factory import available_strategies
from app.rag.vectorstores.base import VectorStore, namespace_for
from app.repositories.bots import BotRepository
from app.routers.deps import owned_bot
from app.schemas import BotCreate, BotOut, BotSummaryOut, BotUpdate, ChatRequest, ChunkingStrategyOut
from app.services.analytics import AnalyticsService
from app.services.chat import ChatService

router = APIRouter(tags=["bots"])


@router.get("/meta/chunking-strategies", response_model=list[ChunkingStrategyOut])
def chunking_strategies():
    return available_strategies()


@router.get("/bots", response_model=list[BotSummaryOut])
def list_bots(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [
        BotSummaryOut.model_validate(s.bot).model_copy(
            update={"document_count": s.document_count, "queries_this_month": s.queries_this_month}
        )
        for s in BotRepository(db).list_for_owner(user.id)
    ]


@router.post("/bots", response_model=BotOut, status_code=status.HTTP_201_CREATED)
def create_bot(body: BotCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bot = BotRepository(db).add(
        Bot(owner_id=user.id, name=body.name, public_key=new_public_key(), allowed_origins=[])
    )
    db.commit()
    return bot


@router.get("/bots/{bot_id}", response_model=BotOut)
def get_bot(bot: Bot = Depends(owned_bot)):
    return bot


@router.patch("/bots/{bot_id}", response_model=BotOut)
def update_bot(body: BotUpdate, bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(bot, field, value)
    db.commit()
    return bot


@router.post("/bots/{bot_id}/rotate-key", response_model=BotOut)
def rotate_key(bot: Bot = Depends(owned_bot), db: Session = Depends(get_db)):
    """Invalidate a leaked/abused widget key: old embeds stop working immediately."""
    bot.public_key = new_public_key()
    db.commit()
    return bot


@router.delete("/bots/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bot(
    bot: Bot = Depends(owned_bot),
    db: Session = Depends(get_db),
    store: VectorStore = Depends(get_vector_store),
):
    files = [d.file_path for d in bot.documents if d.file_path]
    store.drop_namespace(namespace_for(bot.id))
    BotRepository(db).delete(bot)
    db.commit()
    for f in files:
        Path(f).unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/bots/{bot_id}/chat")
def playground_chat(
    body: ChatRequest,
    bot: Bot = Depends(owned_bot),
    chat: ChatService = Depends(get_chat_service),
):
    return StreamingResponse(
        chat.chat_turn(bot, body.question, body.conversation_id, "playground"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/bots/{bot_id}/analytics")
def analytics(
    days: int = Query(30, ge=1, le=365),
    bot: Bot = Depends(owned_bot),
    db: Session = Depends(get_db),
):
    return AnalyticsService(db).overview(bot.id, days=days)
