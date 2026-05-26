"""
SubscriptionMiddleware — majburiy kanal obunasini tekshiradi.
AuthMiddleware dan KEYIN ishga tushirilishi kerak.
"""

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from asgiref.sync import sync_to_async
from django.conf import settings

logger = logging.getLogger("bot")

SUB_CHECK_CB = "sub:check"


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

        # Adminlar tekshirilmaydi
        if tg_id in getattr(settings, "ADMIN_IDS", []):
            return await handler(event, data)

        # "sub:check" callback doim o'tishi kerak (check button ishlashi uchun)
        if isinstance(event, CallbackQuery) and event.data == SUB_CHECK_CB:
            return await handler(event, data)

        # Admin callback lari o'tadi
        if isinstance(event, CallbackQuery) and (event.data or "").startswith("adm:"):
            return await handler(event, data)

        bot: Bot = data["bot"]
        not_subscribed = await _check_subscriptions(bot, tg_id)

        if not not_subscribed:
            return await handler(event, data)

        # Obuna qilinmagan kanallar bor
        b = InlineKeyboardBuilder()
        for ch in not_subscribed:
            b.row(InlineKeyboardButton(text=f"📡 {ch.title}", url=ch.link))
        b.row(InlineKeyboardButton(text="✅ Obuna bo'ldim — Tekshirish", callback_data=SUB_CHECK_CB))

        text = (
            "🔒 <b>Majburiy obuna</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "Botdan foydalanish uchun quyidagi kanallarga\n"
            "obuna bo'lishingiz shart:\n\n"
            + "\n".join(f"📡 <b>{ch.title}</b>" for ch in not_subscribed)
            + "\n\nObuna bo'lgach <b>✅ Tekshirish</b> tugmasini bosing."
        )

        if isinstance(event, Message):
            await event.answer(text, parse_mode="HTML", reply_markup=b.as_markup())
        elif isinstance(event, CallbackQuery):
            await event.answer("⛔ Avval kanallarga obuna bo'ling!", show_alert=True)
            try:
                await event.message.answer(text, parse_mode="HTML", reply_markup=b.as_markup())
            except Exception:
                pass
        return  # handler chaqirilmaydi


@sync_to_async
def _load_active_channels():
    from apps.users.models import RequiredChannel
    return list(RequiredChannel.objects.filter(is_active=True))


async def _check_subscriptions(bot: Bot, user_id: int) -> list:
    """Obuna bo'lmagan kanallar ro'yxatini qaytaradi."""
    channels = await _load_active_channels()
    if not channels:
        return []

    not_subscribed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch.channel_id, user_id)
            if member.status in ("left", "kicked", "banned"):
                not_subscribed.append(ch)
        except Exception as e:
            logger.warning("Kanal tekshirishda xato (id=%s): %s", ch.channel_id, e)
    return not_subscribed
