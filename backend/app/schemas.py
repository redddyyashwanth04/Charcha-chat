from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

UtcDatetime = Annotated[
    datetime, PlainSerializer(lambda d: d.isoformat() + "Z", return_type=str, when_used="json")
]

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth
class RegisterIn(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=128)


class UserOut(ORM):
    id: int
    email: str


class TokenOut(BaseModel):
    access_token: str
    user: UserOut


# ---- conversations
class ConversationOut(ORM):
    id: int
    title: str
    pinned: bool
    created_at: UtcDatetime
    updated_at: UtcDatetime


class RenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class PinIn(BaseModel):
    pinned: bool


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: UtcDatetime
    thread_count: int = 0


# ---- chat
class ChatIn(BaseModel):
    conversation_id: int | None = None
    message: str = Field(min_length=1, max_length=20000)


# ---- doubts
class DoubtIn(BaseModel):
    thread_id: int | None = None  # continue this thread
    parent_thread_id: int | None = None  # start a nested thread under this one
    question: str = Field(min_length=1, max_length=5000)
    quote: str | None = Field(default=None, max_length=2000)


class DoubtMessageOut(ORM):
    id: int
    role: str
    content: str


class ThreadOut(ORM):
    id: int
    parent_thread_id: int | None
    quote: str | None
    depth: int
    created_at: UtcDatetime
    messages: list[DoubtMessageOut]


# ---- search
class SearchHit(BaseModel):
    kind: str  # message | doubt
    conversation_id: int
    conversation_title: str
    message_id: int
    thread_id: int | None = None
    snippet: str
