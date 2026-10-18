from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm import get_llm
from app.llm.base import LLMClient
from app.models import User
from app.ratelimit import limiter
from app.schemas import ChatIn
from app.security import current_user
from app.services import chat_service

router = APIRouter(prefix="/api", tags=["chat"])
NDJSON = "application/x-ndjson"


@router.post("/chat")
def chat(
    body: ChatIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    """conversation_id=null starts a new chat; it is created now, so empty chats never exist."""
    limiter.check(user.id)
    prep = chat_service.prepare_chat(db, user, body.conversation_id, body.message)
    return StreamingResponse(chat_service.run_chat(prep, llm), media_type=NDJSON)


@router.post("/conversations/{conversation_id}/regenerate")
def regenerate(
    conversation_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    limiter.check(user.id)
    prep = chat_service.prepare_regenerate(db, user, conversation_id)
    return StreamingResponse(chat_service.run_chat(prep, llm), media_type=NDJSON)
