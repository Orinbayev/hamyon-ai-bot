"""
Auth middleware — Message va CallbackQuery uchun db_user inject qiladi.
"""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from apps.users.models import TelegramUser

logger = logging.getLogger("bot")


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

        full_name = tg_user.full_name or tg_user.username or str(tg_user.id)
        db_user, created = await TelegramUser.objects.aupdate_or_create(
            telegram_id=tg_user.id,
            defaults={"full_name": full_name, "username": tg_user.username},
        )
        if created:
            logger.info("Yangi foydalanuvchi: %s (%d)", full_name, tg_user.id)

        data["db_user"] = db_user
        return await handler(event, data)
