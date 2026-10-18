from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import ConversationOut, MessageOut, PinIn, RenameIn, SearchHit
from app.security import current_user
from app.services import conversation_service as svc

router = APIRouter(prefix="/api", tags=["conversations"])


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    q: str | None = Query(default=None, max_length=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return svc.list_conversations(db, user, q)


@router.get("/conversations/{conversation_id}", response_model=list[MessageOut])
def get_conversation(
    conversation_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    conv = svc.get_owned(db, user, conversation_id)
    return svc.messages_with_thread_counts(db, conv)


@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
def rename_conversation(
    conversation_id: int,
    body: RenameIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return svc.rename(db, user, conversation_id, body.title)


@router.patch("/conversations/{conversation_id}/pin", response_model=ConversationOut)
def pin_conversation(
    conversation_id: int,
    body: PinIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return svc.set_pinned(db, user, conversation_id, body.pinned)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    svc.delete(db, user, conversation_id)
    return Response(status_code=204)


@router.get("/conversations/{conversation_id}/export")
def export_conversation(
    conversation_id: int,
    include_doubts: bool = True,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    conv = svc.get_owned(db, user, conversation_id)
    body = svc.export_markdown(db, user, conversation_id, include_doubts)
    filename = "".join(c if c.isalnum() or c in "-_ " else "" for c in conv.title).strip() or "chat"
    return Response(
        body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.md"'},
    )


@router.get("/search", response_model=list[SearchHit])
def search(
    q: str = Query(min_length=1, max_length=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return svc.search(db, user, q)
