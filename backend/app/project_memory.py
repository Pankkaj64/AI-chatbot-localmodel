from sqlmodel import select

from app.models import ProjectNote
from db.database import SessionLocal


async def save_project_note(project_name: str, note: str) -> str:
    """Store a note in PostgreSQL for future project chats."""
    note = note.strip()[:5000]

    if not note:
        raise ValueError("The note cannot be empty.")

    async with SessionLocal() as session:
        session.add(ProjectNote(project_name=project_name, note=note))
        await session.commit()

    return "Project note saved."


async def get_recent_project_notes(
    project_name: str,
    limit: int = 8,
) -> list[str]:
    """Load recent project notes from PostgreSQL."""
    statement = (
        select(ProjectNote)
        .where(ProjectNote.project_name == project_name)
        .order_by(ProjectNote.id.desc())
        .limit(limit)
    )

    async with SessionLocal() as session:
        result = await session.exec(statement)
        notes = result.all()

    # Show older notes first, so they read chronologically in the prompt.
    return [item.note for item in reversed(notes)]