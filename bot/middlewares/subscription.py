"""
SubscriptionMiddleware — majburiy kanal obunasini tekshiradi.

Flow:
  1. Foydalanuvchi "1-Kanal" tugmasini bosadi → URL + "✅ Zayafka yubordim" ko'rinadi
  2. Foydalanuvchi kanalga o'tib zayafka yuboradi
  3. "✅ Zayafka yubordim" tugmasini bosadi → kanal tasdiqlangan
  4. Barcha kanallar tasdiqlangandan keyin "Tekshirish" ishlaydi
"""

import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
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

SUB_CHECK_CB   = "sub:check"
SUB_VISIT_CB   = "sub:visit"    # sub:visit:{channel_db_id}
SUB_CONFIRM_CB = "sub:confirm"  # sub:confirm:{channel_db_id}

# Tasdiqlangan kanallar: {user_id: {channel_db_id, ...}}
_VISITED: dict[int, set[int]] = {}

# 5 daqiqa pass: {user_id: timestamp}
_PASS_CACHE: dict[int, float] = {}
PASS_TTL = 300

# Obuna xabarining joylashuvi: {user_id: (chat_id, message_id)}
_SUB_MESSAGES: dict[int, tuple[int, int]] = {}


def _sub_keyboard(channels: list, visited: set | None = None, open_ch=None) -> Any:
    """
    channels  — barcha aktiv kanallar
    visited   — tasdiqlangan kanal db id'lari (✅ ko'rsatish uchun)
    open_ch   — URL va "Zayafka yubordim" tugmasi ko'rsatiladigan kanal
    """
    b = InlineKeyboardBuilder()
    visited = visited or set()
    for i, ch in enumerate(channels):
        label = f"✅ {i + 1}-Kanal" if ch.id in visited else f"{i + 1}-Kanal"
        b.row(InlineKeyboardButton(
            text=label,
            callback_data=f"{SUB_VISIT_CB}:{ch.id}",
        ))
    if open_ch:
        if open_ch.link:
            b.row(InlineKeyboardButton(
                text="🔗 Kanalga o'ting ↗",
                url=open_ch.link,
            ))
        # "Zayafka yubordim" faqat hali tasdiqlanmagan kanallar uchun
        if open_ch.id not in visited:
            b.row(InlineKeyboardButton(
                text="✅ Zayafka yubordim",
                callback_data=f"{SUB_CONFIRM_CB}:{open_ch.id}",
            ))
    b.row(InlineKeyboardButton(text="✅ Tekshirish", callback_data=SUB_CHECK_CB))
    return b.as_markup()


def _sub_text(n: int) -> str:
    kanallar = "kanalga" if n == 1 else "ta kanalga"
    count = "" if n == 1 else f"{n} "
    return (
        f"🔒 Botdan foydalanish uchun {count}{kanallar} zayafka yuboring!\n\n"
        f"📌 Har bir kanal tugmasini bosing → kanalga o'ting → "
        f"\"Zayafka yuborish\" tugmasini bosing → "
        f"\"✅ Zayafka yubordim\" tugmasini bosing."
    )


def mark_visited(user_id: int, channel_db_id: int) -> None:
    _VISITED.setdefault(user_id, set()).add(channel_db_id)


def has_visited_all(user_id: int, channels: list) -> bool:
    """Barcha kanallarga zayafka tasdiqlangan mi?"""
    visited = _VISITED.get(user_id, set())
    return all(ch.id in visited for ch in channels)


def set_pass_cache(user_id: int) -> None:
    _PASS_CACHE[user_id] = time.time()


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

        # sub:check, sub:visit:*, sub:confirm:*, adm:* — har doim o'tadi
        if isinstance(event, CallbackQuery):
            cd = event.data or ""
            if (
                cd == SUB_CHECK_CB
                or cd.startswith(f"{SUB_VISIT_CB}:")
                or cd.startswith(f"{SUB_CONFIRM_CB}:")
                or cd.startswith("adm:")
            ):
                return await handler(event, data)

        # Pass cache aktiv bo'lsa — o'tkazib yuborish
        if time.time() - _PASS_CACHE.get(tg_id, 0) < PASS_TTL:
            return await handler(event, data)

        channels = await _load_active_channels()
        if not channels:
            return await handler(event, data)

        # Barcha kanallar tasdiqlangan bo'lsa — pass cacheni yangilab o'tkazish
        if has_visited_all(tg_id, channels):
            set_pass_cache(tg_id)
            return await handler(event, data)

        # Obuna xabarini ko'rsatish va xabar joylashuvini saqlash
        visited = _VISITED.get(tg_id, set())
        kb = _sub_keyboard(channels, visited=visited)
        text = _sub_text(len(channels))

        if isinstance(event, Message):
            msg = await event.answer(text, reply_markup=kb)
            _SUB_MESSAGES[tg_id] = (msg.chat.id, msg.message_id)
        elif isinstance(event, CallbackQuery):
            await event.answer("⛔ Avval kanallarga zayafka yuboring!", show_alert=True)
            try:
                msg = await event.message.answer(text, reply_markup=kb)
                _SUB_MESSAGES[tg_id] = (msg.chat.id, msg.message_id)
            except Exception:
                pass
        return


@sync_to_async
def _load_active_channels():
    from apps.users.models import RequiredChannel
    return list(RequiredChannel.objects.filter(is_active=True))


@sync_to_async
def _get_channel_by_tg_id(tg_id: int):
    from apps.users.models import RequiredChannel
    return RequiredChannel.objects.filter(channel_id=tg_id, is_active=True).first()
