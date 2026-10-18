"""Conversation CRUD, search and export. Every query is scoped to the owning user."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import Conversation, DoubtMessage, DoubtThread, Message, User, utcnow
from app.schemas import MessageOut, SearchHit


def get_owned(db: Session, user: User, conversation_id: int) -> Conversation:
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    if conv is None:
        raise NotFoundError("Conversation not found")
    return conv


def list_conversations(db: Session, user: User, q: str | None = None) -> list[Conversation]:
    stmt = select(Conversation).where(Conversation.user_id == user.id)
    if q:
        stmt = stmt.where(func.lower(Conversation.title).contains(q.lower(), autoescape=True))
    stmt = stmt.order_by(Conversation.pinned.desc(), Conversation.updated_at.desc())
    return list(db.scalars(stmt))


def messages_with_thread_counts(db: Session, conv: Conversation) -> list[MessageOut]:
    counts = dict(
        db.execute(
            select(DoubtThread.message_id, func.count(DoubtThread.id))
            .join(Message, Message.id == DoubtThread.message_id)
            .where(Message.conversation_id == conv.id)
            .group_by(DoubtThread.message_id)
        ).all()
    )
    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
            thread_count=counts.get(m.id, 0),
        )
        for m in conv.messages
    ]


def rename(db: Session, user: User, conversation_id: int, title: str) -> Conversation:
    conv = get_owned(db, user, conversation_id)
    conv.title = title.strip()
    db.commit()
    return conv


def set_pinned(db: Session, user: User, conversation_id: int, pinned: bool) -> Conversation:
    conv = get_owned(db, user, conversation_id)
    conv.pinned = pinned
    db.commit()
    return conv


def delete(db: Session, user: User, conversation_id: int) -> None:
    conv = get_owned(db, user, conversation_id)
    db.delete(conv)  # ORM cascade removes messages, threads and doubt messages
    db.commit()


def touch(conv: Conversation) -> None:
    conv.updated_at = utcnow()


def _snippet(text: str, q: str, width: int = 60) -> str:
    i = text.lower().find(q.lower())
    start = max(0, i - width)
    end = min(len(text), i + len(q) + width)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + " ".join(text[start:end].split()) + suffix


def search(db: Session, user: User, q: str, limit: int = 30) -> list[SearchHit]:
    q = q.strip()
    if not q:
        return []
    pattern = func.lower(Message.content).contains(q.lower(), autoescape=True)
    hits: list[SearchHit] = []

    rows = db.execute(
        select(Message, Conversation)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.user_id == user.id, pattern)
        .order_by(Message.id.desc())
        .limit(limit)
    ).all()
    for m, c in rows:
        hits.append(
            SearchHit(
                kind="message",
                conversation_id=c.id,
                conversation_title=c.title,
                message_id=m.id,
                snippet=_snippet(m.content, q),
            )
        )

    drows = db.execute(
        select(DoubtMessage, DoubtThread, Message, Conversation)
        .join(DoubtThread, DoubtThread.id == DoubtMessage.thread_id)
        .join(Message, Message.id == DoubtThread.message_id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(
            Conversation.user_id == user.id,
            func.lower(DoubtMessage.content).contains(q.lower(), autoescape=True),
        )
        .order_by(DoubtMessage.id.desc())
        .limit(limit)
    ).all()
    for dm, t, m, c in drows:
        hits.append(
            SearchHit(
                kind="doubt",
                conversation_id=c.id,
                conversation_title=c.title,
                message_id=m.id,
                thread_id=t.id,
                snippet=_snippet(dm.content, q),
            )
        )
    return hits[:limit]


def export_markdown(db: Session, user: User, conversation_id: int, include_doubts: bool) -> str:
    conv = get_owned(db, user, conversation_id)
    lines = [f"# {conv.title}", ""]
    for m in conv.messages:
        who = "You" if m.role == "user" else "Assistant"
        lines += [f"### {who}", "", m.content, ""]
        if include_doubts and m.threads:
            for t in m.threads:
                label = (t.quote or (t.messages[0].content if t.messages else "Doubt"))[:80]
                lines += [f"<details><summary>Doubt: {label}</summary>", ""]
                for dm in t.messages:
                    speaker = "**Q:**" if dm.role == "user" else "**A:**"
                    lines += [f"{speaker} {dm.content}", ""]
                lines += ["</details>", ""]
    return "\n".join(lines)
