"""Streaming chat. Main-chat context is built from main messages ONLY.

Doubt threads are deliberately never read here: that is the product's core promise.
"""

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.errors import AppError, ValidationError
from app.llm.base import LLMClient, Turn
from app.models import Conversation, Message, User
from app.prompts import MAIN_SYSTEM, TITLE_SYSTEM
from app.services import conversation_service as convs

logger = logging.getLogger(__name__)


def event(obj: dict) -> str:
    return json.dumps(obj) + "\n"  # NDJSON: one JSON event per line


def trim_history(turns: list[Turn], budget_chars: int) -> list[Turn]:
    """Drop the oldest whole turns until the history fits. Always keeps the latest user turn."""
    total = sum(len(t) for _, t in turns)
    start = 0
    while total > budget_chars and start < len(turns) - 1:
        total -= len(turns[start][1])
        start += 1
    # never start the history on an assistant turn
    while start < len(turns) - 1 and turns[start][0] == "assistant":
        start += 1
    return turns[start:]


def history_turns(db: Session, conversation_id: int) -> list[Turn]:
    rows = db.scalars(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
    ).all()
    turns = [(m.role, m.content) for m in rows]
    return trim_history(turns, get_settings().context_char_budget)


@dataclass
class ChatPrep:
    conversation_id: int
    user_message_id: int
    is_new: bool
    needs_title: bool
    user_text: str
    turns: list[Turn]


def prepare_chat(db: Session, user: User, conversation_id: int | None, text: str) -> ChatPrep:
    text = text.strip()
    if not text:
        raise ValidationError("Message is empty")
    is_new = conversation_id is None
    if is_new:
        conv = Conversation(user_id=user.id, title=text[:40])
        db.add(conv)
        db.flush()
    else:
        conv = convs.get_owned(db, user, conversation_id)
    msg = Message(conversation_id=conv.id, role="user", content=text)
    db.add(msg)
    convs.touch(conv)
    db.commit()
    count = db.query(Message).filter(Message.conversation_id == conv.id).count()
    return ChatPrep(
        conversation_id=conv.id,
        user_message_id=msg.id,
        is_new=is_new,
        needs_title=count == 1,
        user_text=text,
        turns=history_turns(db, conv.id),
    )


def prepare_regenerate(db: Session, user: User, conversation_id: int) -> ChatPrep:
    conv = convs.get_owned(db, user, conversation_id)
    if not conv.messages or conv.messages[-1].role != "assistant":
        raise ValidationError("There is no reply to regenerate")
    db.delete(conv.messages[-1])  # its doubt threads go with it
    db.commit()
    db.refresh(conv)
    last_user = conv.messages[-1]
    return ChatPrep(
        conversation_id=conv.id,
        user_message_id=last_user.id,
        is_new=False,
        needs_title=False,
        user_text=last_user.content,
        turns=history_turns(db, conv.id),
    )


def _save_assistant(conversation_id: int, text: str, model: str) -> int:
    with SessionLocal() as db:
        msg = Message(conversation_id=conversation_id, role="assistant", content=text, model=model)
        db.add(msg)
        conv = db.get(Conversation, conversation_id)
        if conv is not None:
            convs.touch(conv)
        db.commit()
        return msg.id


def make_title(llm: LLMClient, user_text: str, answer: str) -> str:
    fallback = user_text.strip()[:40]
    try:
        raw = llm.complete(
            TITLE_SYSTEM,
            [("user", f"User: {user_text[:500]}\n\nAssistant: {answer[:500]}")],
            max_tokens=24,
        )
    except Exception:  # a failed title must never fail the chat
        logger.warning("title generation failed", exc_info=True)
        return fallback
    title = re.sub(
        r"^[\"'#*\s]+|[\"'*\s.]+$", "", raw.strip().splitlines()[0] if raw.strip() else ""
    )
    return title[:60] or fallback


def run_chat(prep: ChatPrep, llm: LLMClient) -> Iterator[str]:
    if prep.is_new:
        yield event({"type": "conversation", "id": prep.conversation_id})
    yield event({"type": "user", "id": prep.user_message_id})

    parts: list[str] = []
    try:
        for piece in llm.stream(MAIN_SYSTEM, prep.turns):
            parts.append(piece)
            yield event({"type": "delta", "text": piece})
    except GeneratorExit:
        # the user pressed Stop (client disconnected): keep what was generated so far
        partial = "".join(parts).strip()
        if partial:
            _save_assistant(prep.conversation_id, partial, llm.label)
        raise
    except Exception as exc:
        logger.exception("chat stream failed")
        partial = "".join(parts).strip()
        if partial:
            _save_assistant(prep.conversation_id, partial, llm.label)
        message = exc.message if isinstance(exc, AppError) else "The AI provider failed."
        yield event({"type": "error", "message": message})
        return

    answer = "".join(parts).strip()
    if not answer:
        yield event({"type": "error", "message": "The model returned an empty response."})
        return
    assistant_id = _save_assistant(prep.conversation_id, answer, llm.label)
    yield event({"type": "done", "id": assistant_id})

    if prep.needs_title:
        title = make_title(llm, prep.user_text, answer)
        with SessionLocal() as db:
            conv = db.get(Conversation, prep.conversation_id)
            if conv is not None:
                conv.title = title
                db.commit()
        yield event({"type": "title", "title": title})
