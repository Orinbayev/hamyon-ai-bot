"""
SubscriptionMiddleware — majburiy kanal obunasini tekshiradi.

Ikki rejim:
  display_check  — ko'rsatish uchun: public=aniq tekshir, private=exception→ko'rsat
  strict_check   — o'tkazish uchun:  public=aniq tekshir, private=exception→o'tkaz

Natija:
  - Public kanal, a'zo emas          → blok (ko'rsat VA o'tkaz olmaydi)
  - Public kanal, a'zo               → o'tadi
  - Private kanal, bot admin emas    → message ko'rsatiladi, Tekshirish bosganda o'tadi
  - Private kanal, bot admin         → xuddi public kabi aniq tekshiriladi
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
NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

# Tekshirish bosilgandan keyingi qisqa oyna (sekund):
# bu vaqt ichida kanal obunasiz ham xabar yozish mumkin
_PASS_CACHE: dict[int, float] = {}  # user_id → timestamp
PASS_TTL = 300  # 5 daqiqa


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

        # Qisqa "pass" oynasi aktiv bo'lsa o'tkazib yuborish
        ts = _PASS_CACHE.get(tg_id, 0)
        if time.time() - ts < PASS_TTL:
            return await handler(event, data)

        bot: Bot = data["bot"]

        # Ko'rsatish uchun tekshiruv (private kanal exception → ko'rsat)
        to_show = await _channels_to_show(bot, tg_id)

        if not to_show:
            return await handler(event, data)

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
        return  # handler chaqirilmaydi


@sync_to_async
def _load_active_channels():
    from apps.users.models import RequiredChannel
    return list(RequiredChannel.objects.filter(is_active=True))


async def _channels_to_show(bot: Bot, user_id: int) -> list:
    """
    Ko'rsatish ro'yxati:
      - Public kanal → aniq tekshiradi: "left"/"kicked" → qo'shadi
      - Private kanal (exception) → har doim qo'shadi (ko'rsatish uchun)
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
            # member/administrator/creator/restricted → o'tadi
        except Exception as e:
            logger.debug("get_chat_member xatosi (id=%s): %s", ch.channel_id, e)
            result.append(ch)  # tekshirib bo'lmadi → ko'rsat (ehtiyot uchun)
    return result


async def _channels_blocking(bot: Bot, user_id: int) -> list:
    """
    O'tkazmaslik uchun ro'yxat (faqat aniq tekshirib bo'linadigan kanallar):
      - Public kanal yoki bot admin → "left"/"kicked" → qo'shadi
      - Exception → o'tkazadi (tekshirib bo'lmadi → yumshoq cheklov)
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
        except Exception as e:
            logger.debug("Kanal tekshirib bo'lmadi, o'tkazilmoqda (id=%s): %s", ch.channel_id, e)
    return result


def set_pass_cache(user_id: int) -> None:
    """Foydalanuvchini PASS_TTL sekund davomida obuna tekshiruvdan o'tkazib yuborish."""
    _PASS_CACHE[user_id] = time.time()
