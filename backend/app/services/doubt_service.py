"""Doubt threads: side conversations scoped to ONE assistant reply.

Context sent to the model = original question + that reply + (for nested doubts) the chain of
ancestor threads + this thread's own messages. Nothing else from the chat is ever included.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.errors import AppError, NotFoundError, ValidationError
from app.llm.base import LLMClient, Turn
from app.models import Conversation, DoubtMessage, DoubtThread, Message, User
from app.prompts import BRANCH_BLOCK, DOUBT_SYSTEM
from app.services.chat_service import event

logger = logging.getLogger(__name__)


def get_owned_reply(db: Session, user: User, message_id: int) -> Message:
    msg = db.scalar(
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Message.id == message_id,
            Message.role == "assistant",
            Conversation.user_id == user.id,
        )
    )
    if msg is None:
        raise NotFoundError("Reply not found")
    return msg


def list_threads(db: Session, user: User, message_id: int) -> list[DoubtThread]:
    msg = get_owned_reply(db, user, message_id)
    return list(msg.threads)


def delete_thread(db: Session, user: User, thread_id: int) -> None:
    thread = db.scalar(
        select(DoubtThread)
        .join(Message, Message.id == DoubtThread.message_id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(DoubtThread.id == thread_id, Conversation.user_id == user.id)
    )
    if thread is None:
        raise NotFoundError("Doubt thread not found")
    db.delete(thread)
    db.commit()


def with_quote(text: str, quote: str | None) -> str:
    return f'(About this passage: "{quote}")\n\n{text}' if quote else text


def _thread_turns(thread: DoubtThread) -> list[Turn]:
    turns: list[Turn] = []
    for i, m in enumerate(thread.messages):
        text = with_quote(m.content, thread.quote) if i == 0 and m.role == "user" else m.content
        turns.append((m.role, text))
    return turns


def _render_chain(ancestors: list[DoubtThread]) -> str:
    blocks = []
    for n, t in enumerate(ancestors, 1):
        header = f"Thread {n}" + (f' (about: "{t.quote}")' if t.quote else "")
        body = "\n".join(
            f"{'User' if m.role == 'user' else 'Tutor'}: {m.content}" for m in t.messages
        )
        blocks.append(f"{header}\n{body}")
    return "\n\n".join(blocks)


@dataclass
class DoubtPrep:
    thread_id: int
    is_new_thread: bool
    system: str
    turns: list[Turn]


def build_context(reply: Message, original_question: str | None, thread: DoubtThread):
    """Pure function that assembles the scoped prompt, easy to unit-test."""
    ancestors: list[DoubtThread] = []
    node = thread.parent
    while node is not None:
        ancestors.insert(0, node)
        node = node.parent
    branch = BRANCH_BLOCK.format(chain=_render_chain(ancestors)) if ancestors else ""
    system = DOUBT_SYSTEM.format(
        question=original_question or "(not available)", answer=reply.content, branch=branch
    )
    return system, _thread_turns(thread)


def prepare_doubt(
    db: Session,
    user: User,
    message_id: int,
    question: str,
    thread_id: int | None,
    parent_thread_id: int | None,
    quote: str | None,
) -> DoubtPrep:
    question = question.strip()
    if not question:
        raise ValidationError("Question is empty")
    reply = get_owned_reply(db, user, message_id)

    is_new = thread_id is None
    if is_new:
        parent = None
        depth = 1
        if parent_thread_id is not None:
            parent = db.get(DoubtThread, parent_thread_id)
            if parent is None or parent.message_id != reply.id:
                raise NotFoundError("Parent doubt thread not found")
            depth = parent.depth + 1
        if depth > get_settings().max_doubt_depth:
            raise ValidationError(
                f"Doubts can only be nested {get_settings().max_doubt_depth} levels deep"
            )
        thread = DoubtThread(
            message_id=reply.id, parent_thread_id=parent_thread_id, quote=quote, depth=depth
        )
        db.add(thread)
        db.flush()
    else:
        thread = db.get(DoubtThread, thread_id)
        if thread is None or thread.message_id != reply.id:
            raise NotFoundError("Doubt thread not found")

    db.add(DoubtMessage(thread_id=thread.id, role="user", content=question))
    db.commit()
    db.refresh(thread)

    original_question = db.scalar(
        select(Message.content)
        .where(
            Message.conversation_id == reply.conversation_id,
            Message.role == "user",
            Message.id < reply.id,
        )
        .order_by(Message.id.desc())
        .limit(1)
    )
    system, turns = build_context(reply, original_question, thread)
    return DoubtPrep(thread_id=thread.id, is_new_thread=is_new, system=system, turns=turns)


def _save_answer(thread_id: int, text: str) -> int:
    with SessionLocal() as db:
        m = DoubtMessage(thread_id=thread_id, role="assistant", content=text)
        db.add(m)
        db.commit()
        return m.id


def run_doubt(prep: DoubtPrep, llm: LLMClient) -> Iterator[str]:
    yield event({"type": "thread", "id": prep.thread_id, "new": prep.is_new_thread})
    parts: list[str] = []
    try:
        for piece in llm.stream(prep.system, prep.turns):
            parts.append(piece)
            yield event({"type": "delta", "text": piece})
    except GeneratorExit:
        partial = "".join(parts).strip()
        if partial:
            _save_answer(prep.thread_id, partial)
        raise
    except Exception as exc:
        logger.exception("doubt stream failed")
        message = exc.message if isinstance(exc, AppError) else "The AI provider failed."
        yield event({"type": "error", "message": message})
        return
    answer = "".join(parts).strip()
    if not answer:
        yield event({"type": "error", "message": "The model returned an empty response."})
        return
    yield event({"type": "done", "id": _save_answer(prep.thread_id, answer)})
