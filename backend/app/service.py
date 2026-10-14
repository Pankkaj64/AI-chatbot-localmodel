from sqlalchemy import delete, func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Message


class ChatService:
    async def get_recent_messages(self, session_id: str, session: AsyncSession, limit: int = 10):
        """Last `limit` messages of a session, oldest first (the order the model needs)."""
        statement = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(col(Message.id).desc())
            .limit(limit)
        )
        result = await session.exec(statement)
        return list(reversed(result.all()))

    async def save_messages(self, session: AsyncSession, *messages: Message):
        session.add_all(messages)
        await session.commit()

    async def list_sessions(self, session: AsyncSession):
        """The first message of every session, newest session first."""
        first_ids = select(func.min(Message.id)).group_by(Message.session_id)
        statement = (
            select(Message)
            .where(col(Message.id).in_(first_ids))
            .order_by(col(Message.timestamp).desc())
        )
        result = await session.exec(statement)
        return result.all()

    async def get_history(self, session_id: str, session: AsyncSession):
        statement = (
            select(Message).where(Message.session_id == session_id).order_by(col(Message.id))
        )
        result = await session.exec(statement)
        return result.all()

    async def delete_session(self, session_id: str, session: AsyncSession):
        await session.exec(delete(Message).where(col(Message.session_id) == session_id))
        await session.commit()
