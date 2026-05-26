"""
SubscriptionMiddleware — majburiy kanal obunasini tekshiradi.

Tugmalar:
  sub:visit:{db_id}  — kanalga o'tish + "bosildi" belgisi qo'yish
  sub:check          — tekshirish (faqat sub:visit bosilgandan keyin ishlaydi)
"""

import logging
import time
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
SUB_VISIT_CB = "sub:visit"   # sub:visit:{channel_db_id}

NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

# Bosib chiqqan kanallar: {user_id: {channel_db_id, ...}}
_VISITED: dict[int, set[int]] = {}

# Tekshirishdan o'tganlar (5 daqiqa): {user_id: timestamp}
_PASS_CACHE: dict[int, float] = {}
PASS_TTL = 300


def _sub_keyboard(channels: list) -> Any:
    b = InlineKeyboardBuilder()
    for i, ch in enumerate(channels):
        num = NUMS[i] if i < len(NUMS) else f"{i + 1}."
        b.row(InlineKeyboardButton(
            text=f"{num} Zayafka yuborish",
            callback_data=f"{SUB_VISIT_CB}:{ch.id}",
        ))
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

        # sub:check, sub:visit:*, adm:* — har doim o'tadi
        if isinstance(event, CallbackQuery):
            cd = event.data or ""
            if cd == SUB_CHECK_CB or cd.startswith(f"{SUB_VISIT_CB}:") or cd.startswith("adm:"):
                return await handler(event, data)

        # Qisqa pass oynasi aktiv bo'lsa o'tkazib yuborish
        if time.time() - _PASS_CACHE.get(tg_id, 0) < PASS_TTL:
            return await handler(event, data)

        bot: Bot = data["bot"]
        to_show = await _channels_to_show(bot, tg_id)

        if not to_show:
            return await handler(event, data)

        # Ko'rsatish
        kb = _sub_keyboard(to_show)
        text = _sub_text(len(to_show))

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


async def _channels_to_show(bot: Bot, user_id: int) -> list:
    """
    Ko'rsatish uchun: public=aniq tekshir, private/exception=ko'rsat.
    """
    channels = await _load_active_channels()
    if not channels:
        return []
    result = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch.channel_id, user_id)
            if member.status in ("left", "kicked"):
                result.append(ch)
        except Exception:
            result.append(ch)  # tekshirib bo'lmadi → ko'rsat
    return result


async def _channels_strictly_blocking(bot: Bot, user_id: int) -> list:
    """
    Faqat aniq tekshirib bo'ladigan kanallar (public / bot admin).
    Exception → o'tkazadi.
    """
    channels = await _load_active_channels()
    if not channels:
        return []
    result = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch.channel_id, user_id)
            if member.status in ("left", "kicked"):
                result.append(ch)
        except Exception:
            pass  # tekshirib bo'lmadi → yumshoq
    return result


def mark_visited(user_id: int, channel_db_id: int) -> None:
    _VISITED.setdefault(user_id, set()).add(channel_db_id)


def has_visited_any(user_id: int, channels: list) -> bool:
    """Foydalanuvchi kamida bitta kanal tugmasini bosganmi?"""
    visited = _VISITED.get(user_id, set())
    return any(ch.id in visited for ch in channels)


def set_pass_cache(user_id: int) -> None:
    _PASS_CACHE[user_id] = time.time()
