from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm import get_llm
from app.llm.base import LLMClient
from app.models import User
from app.ratelimit import limiter
from app.routers.chat import NDJSON
from app.schemas import DoubtIn, ThreadOut
from app.security import current_user
from app.services import doubt_service

router = APIRouter(prefix="/api", tags=["doubts"])


@router.get("/messages/{message_id}/threads", response_model=list[ThreadOut])
def list_threads(
    message_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return doubt_service.list_threads(db, user, message_id)


@router.post("/messages/{message_id}/doubts")
def ask_doubt(
    message_id: int,
    body: DoubtIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
):
    limiter.check(user.id)
    prep = doubt_service.prepare_doubt(
        db,
        user,
        message_id,
        body.question,
        body.thread_id,
        body.parent_thread_id,
        body.quote,
    )
    return StreamingResponse(doubt_service.run_doubt(prep, llm), media_type=NDJSON)


@router.delete("/threads/{thread_id}", status_code=204)
def delete_thread(
    thread_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    doubt_service.delete_thread(db, user, thread_id)
    return Response(status_code=204)
