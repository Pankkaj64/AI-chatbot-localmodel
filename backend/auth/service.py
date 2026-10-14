from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from auth.models import User
from auth.utils import generate_password_hash


class UserService():
    async def get_user_by_email(self, email: str, session: AsyncSession):
        statement = select(User).where(User.email == email)

        result = await session.exec(statement)
        user = result.first()

        return user

    async def user_exists(self, email: str, session: AsyncSession):
        user = await self.get_user_by_email(email, session)

        return True if user is not None else False


    async def create_user(self, user_data, session):
        user_data_dict = user_data.model_dump(exclude={"password"})
        new_user = User(
            **user_data_dict
        )

        new_user.password_hash = generate_password_hash(user_data.password)

        session.add(new_user)

        await session.commit()

        return new_user