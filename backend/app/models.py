from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel, Text


class Message(SQLModel, table=True):
    """One chat message (user or assistant), grouped by session_id."""

    __tablename__ = "messages"

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    role: str
    content: str = Field(sa_type=Text)
    image_url: str | None = Field(default=None, sa_type=Text)
    cost: float = 0.0
    usage_metadata: dict | None = Field(default=None, sa_column=Column(JSONB(none_as_null=True)))
    model_name: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectChunk(SQLModel, table=True):
    """A project text chunk and its embedding, stored in PostgreSQL."""

    __tablename__ = "project_chunks"
    __table_args__ = (
        UniqueConstraint(
            "project_name", "file_path", "chunk_number",
            name="uq_project_chunk_location",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    project_name: str = Field(index=True)
    file_path: str
    chunk_number: int
    content: str = Field(sa_type=Text)
    embedding: list[float] = Field(sa_column=Column(JSONB, nullable=False))


class ProjectNote(SQLModel, table=True):
    """A saved progress note for continuing work on a project."""

    __tablename__ = "project_notes"

    id: int | None = Field(default=None, primary_key=True)
    project_name: str = Field(index=True)
    note: str = Field(sa_type=Text)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )
