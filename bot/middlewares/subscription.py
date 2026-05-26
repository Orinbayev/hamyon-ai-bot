"""
SubscriptionMiddleware — majburiy kanal obunasini tekshiradi.
AuthMiddleware dan KEYIN ro'yxatdan o'tishi kerak.
"""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    Message,
    TelegramObject,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async
from django.conf import settings

logger = logging.getLogger("bot")

SUB_CHECK_CB = "sub:check"
NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def _sub_keyboard(channels: list) -> Any:
    b = InlineKeyboardBuilder()
    for i, ch in enumerate(channels):
        num = NUMS[i] if i < len(NUMS) else f"{i + 1}."
        b.row(InlineKeyboardButton(text=f"{num} Obuna bo'lish", url=ch.link))
    b.row(InlineKeyboardButton(text="✅ Tekshirish", callback_data=SUB_CHECK_CB))
    return b.as_markup()


def _sub_text(n: int) -> str:
    kanallar = "kanalga" if n == 1 else "ta kanalga"
    count = "" if n == 1 else f"{n} "
    return f"🔒 Botdan foydalanish uchun {count}{kanallar} obuna bo'ling!"


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        db_user = data.get("db_user")
        if not db_user:
            return await handler(event, data)

        tg_user = data.get("event_from_user")
        tg_id = tg_user.id if tg_user else db_user.telegram_id

        # Adminlar o'tadi
        if tg_id in getattr(settings, "ADMIN_IDS", []):
            return await handler(event, data)

        # Tekshiruv tugmasi va admin callbacklar har doim o'tadi
        if isinstance(event, CallbackQuery):
            if event.data == SUB_CHECK_CB or (event.data or "").startswith("adm:"):
                return await handler(event, data)

        bot: Bot = data["bot"]
        not_subscribed = await _check_subscriptions(bot, tg_id)

        if not not_subscribed:
            return await handler(event, data)

        kb = _sub_keyboard(not_subscribed)
        text = _sub_text(len(not_subscribed))

        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb)
        elif isinstance(event, CallbackQuery):
            await event.answer("⛔ Avval kanallarga obuna bo'ling!", show_alert=True)
            try:
                await event.message.answer(text, reply_markup=kb)
            except Exception:
                pass
        return


@sync_to_async
def _load_active_channels():
    from apps.users.models import RequiredChannel
    return list(RequiredChannel.objects.filter(is_active=True))


async def _check_subscriptions(bot: Bot, user_id: int) -> list:
    """Obuna bo'lmagan kanallar ro'yxatini qaytaradi.

    Qoidalar:
    - "left" yoki "kicked" → blok
    - "restricted" (join request yuborgan, kutmoqda) → o'tkazadi
    - Exception (bot admin emas, yoki private kanal) → o'tkazadi
    """
    channels = await _load_active_channels()
    if not channels:
        return []

    not_subscribed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch.channel_id, user_id)
            if member.status in ("left", "kicked"):
                not_subscribed.append(ch)
            # member, administrator, creator, restricted → o'tadi
        except Exception as e:
            # Bot kanalda admin emas yoki kanal tekshirib bo'lmaydi — bloklamaydi
            logger.debug("Kanal tekshirib bo'lmadi (id=%s): %s", ch.channel_id, e)
    return not_subscribed
