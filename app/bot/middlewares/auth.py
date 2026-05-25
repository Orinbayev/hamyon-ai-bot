"""
Auth Middleware — har bir xabarda foydalanuvchi avtomatik aniqlanadi.
telegram_id bo'yicha topiladi yoki yangi yaratiladi.
"""
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from app.database.session import AsyncSessionFactory
from app.models.user import User
from app.repositories.user_repo import UserRepository

logger = logging.getLogger("bot.auth")


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")

        if not tg_user or tg_user.is_bot:
            return await handler(event, data)

        async with AsyncSessionFactory() as session:
            repo = UserRepository(session)
            user, is_new = await repo.get_or_create(
                telegram_id=tg_user.id,
                full_name=tg_user.full_name,
                username=tg_user.username,
                language_code=tg_user.language_code,
            )

            if is_new:
                logger.info("Yangi foydalanuvchi: tg_id=%s name=%r", tg_user.id, tg_user.full_name)

            # Handler uchun inject qilinadi
            data["user"] = user          # User model instance
            data["user_id"] = user.id    # int — tez foydalanish uchun
            data["session"] = session    # AsyncSession

            return await handler(event, data)
