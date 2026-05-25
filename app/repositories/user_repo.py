from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        telegram_id: int,
        full_name: str,
        username: str | None = None,
        language_code: str | None = None,
    ) -> tuple[User, bool]:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            changed = False
            if user.full_name != full_name:
                user.full_name = full_name
                changed = True
            if user.username != username:
                user.username = username
                changed = True
            if changed:
                await self.session.flush()
            return user, False

        user = await self.create(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            language_code=language_code,
        )
        await self.commit()
        return user, True

    async def set_custom_name(self, user: User, name: str) -> User:
        user.custom_name = name.strip()
        await self.session.flush()
        await self.commit()
        return user
