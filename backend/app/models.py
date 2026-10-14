from datetime import datetime, timezone

import sqlalchemy.dialects.postgresql as pg
from sqlmodel import Column, Field, SQLModel, Text


class Message(SQLModel, table=True):
    """One chat message (user or assistant); messages are grouped by session_id."""

    __tablename__ = "messages"

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    role: str
    content: str = Field(sa_type=Text)
    image_url: str | None = Field(default=None, sa_type=Text)
    cost: float = 0.0
    usage_metadata: dict | None = Field(default=None, sa_column=Column(pg.JSONB(none_as_null=True)))
    model_name: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
