"""
SubscriptionMiddleware — majburiy kanal obunasini tekshiradi.

Zayafka flow:
  1. Foydalanuvchi kanal tugmasini bosadi → URL tugma chiqadi
  2. Kanalga o'tib, istalgan xabarni botga FORWARD qiladi
  3. Bot forward'ni taniydi → zayafka tasdiqlanadi
  4. "Tekshirish" bosilganda ruxsat beriladi
"""

import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    Message,
    MessageOriginChannel,
    TelegramObject,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async
from django.conf import settings

logger = logging.getLogger("bot")

SUB_CHECK_CB = "sub:check"
SUB_VISIT_CB = "sub:visit"   # sub:visit:{channel_db_id}

NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

# Zayafka tasdiqlangan kanallar: {user_id: {channel_db_id, ...}}
_ZAYAFKA_DONE: dict[int, set[int]] = {}

# 5 daqiqa pass oynasi: {user_id: timestamp}
_PASS_CACHE: dict[int, float] = {}
PASS_TTL = 300


def _sub_keyboard(channels: list, done: set | None = None, open_ch=None) -> Any:
    """
    channels  — ko'rsatiladigan kanallar
    done      — zayafka/obuna tasdiqlangan kanal db id'lari
    open_ch   — URL tugma ko'rsatiladigan kanal (bosilgandan keyin)
    """
    b = InlineKeyboardBuilder()
    done = done or set()
    for i, ch in enumerate(channels):
        num = NUMS[i] if i < len(NUMS) else f"{i + 1}."
        if ch.id in done:
            label = f"{num} ✅ {ch.title}"
        else:
            label = f"{num} ➡️ {ch.title}"
        b.row(InlineKeyboardButton(
            text=label,
            callback_data=f"{SUB_VISIT_CB}:{ch.id}",
        ))
    if open_ch and open_ch.link:
        b.row(InlineKeyboardButton(
            text=f"🔗 {open_ch.title} — kanalga o'ting ↗",
            url=open_ch.link,
        ))
    b.row(InlineKeyboardButton(text="✅ Tekshirish", callback_data=SUB_CHECK_CB))
    return b.as_markup()


def _sub_text(n: int) -> str:
    kanallar = "kanalga" if n == 1 else "ta kanalga"
    count = "" if n == 1 else f"{n} "
    return (
        f"🔒 Botdan foydalanish uchun {count}{kanallar} obuna bo'ling!\n\n"
        f"📨 Obuna bo'lgach, kanaldan istalgan xabarni shu botga "
        f"<b>forward</b> (yo'naltirish) qiling."
    )


def mark_zayafka_done(user_id: int, channel_db_id: int) -> None:
    _ZAYAFKA_DONE.setdefault(user_id, set()).add(channel_db_id)


def has_zayafka_for_channel(user_id: int, channel_db_id: int) -> bool:
    return channel_db_id in _ZAYAFKA_DONE.get(user_id, set())


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

        # Adminlar to'siqsiz o'tadi
        if tg_id in getattr(settings, "ADMIN_IDS", []):
            return await handler(event, data)

        # sub:check, sub:visit:*, adm:* — har doim o'tadi
        if isinstance(event, CallbackQuery):
            cd = event.data or ""
            if (
                cd == SUB_CHECK_CB
                or cd.startswith(f"{SUB_VISIT_CB}:")
                or cd.startswith("adm:")
            ):
                return await handler(event, data)

        # 5 daqiqalik pass oynasi
        if time.time() - _PASS_CACHE.get(tg_id, 0) < PASS_TTL:
            return await handler(event, data)

        bot: Bot = data["bot"]
        to_show = await _channels_to_show(bot, tg_id)

        if not to_show:
            return await handler(event, data)

        # ── Zayafka aniqlash: kanaldan forward qilingan xabar ────────────────
        if isinstance(event, Message) and event.forward_origin:
            if isinstance(event.forward_origin, MessageOriginChannel):
                fwd_channel_id = event.forward_origin.chat.id
                ch = await _get_required_channel(fwd_channel_id)
                if ch:
                    mark_zayafka_done(tg_id, ch.id)
                    done = _ZAYAFKA_DONE.get(tg_id, set())
                    still_needed = [c for c in to_show if c.id not in done]

                    if still_needed:
                        text = (
                            f"✅ <b>{ch.title}</b> — zayafka qabul qilindi!\n\n"
                            f"Yana {len(still_needed)} ta kanal qoldi 👇"
                        )
                    else:
                        text = (
                            f"✅ <b>{ch.title}</b> — zayafka qabul qilindi!\n\n"
                            "Endi «✅ Tekshirish» tugmasini bosing!"
                        )

                    await event.answer(
                        text,
                        parse_mode="HTML",
                        reply_markup=_sub_keyboard(to_show, done=done),
                    )
                    return
        # ─────────────────────────────────────────────────────────────────────

        # Obuna xabarini ko'rsatish
        done = _ZAYAFKA_DONE.get(tg_id, set())
        kb = _sub_keyboard(to_show, done=done)
        text = _sub_text(len(to_show))

        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb, parse_mode="HTML")
        elif isinstance(event, CallbackQuery):
            await event.answer("⛔ Avval kanallarga obuna bo'ling!", show_alert=True)
            try:
                await event.message.answer(text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
        return


@sync_to_async
def _load_active_channels():
    from apps.users.models import RequiredChannel
    return list(RequiredChannel.objects.filter(is_active=True))


@sync_to_async
def _get_required_channel(channel_tg_id: int):
    """Telegram channel_id bo'yicha RequiredChannel qaytaradi yoki None."""
    from apps.users.models import RequiredChannel
    try:
        return RequiredChannel.objects.get(channel_id=channel_tg_id, is_active=True)
    except RequiredChannel.DoesNotExist:
        return None


async def _channels_to_show(bot: Bot, user_id: int) -> list:
    """
    Ko'rsatish uchun kanallar:
    public (bot admin) — API tekshiruvi, left/kicked → ko'rsat.
    private / exception → har doim ko'rsat.
    """
    channels = await _load_active_channels()
    result = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch.channel_id, user_id)
            if member.status in ("left", "kicked"):
                result.append(ch)
        except Exception:
            result.append(ch)
    return result


async def _channels_still_blocking(bot: Bot, user_id: int) -> list:
    """
    Hali ruxsat bermayotgan kanallar.
    Kanal o'tadi agar:
      - API orqali obuna tasdiqlansa (public/bot admin)  YOKI
      - Zayafka yuborilgan bo'lsa
    """
    channels = await _load_active_channels()
    result = []
    for ch in channels:
        # 1. Zayafka tasdiqlanganligi
        if has_zayafka_for_channel(user_id, ch.id):
            continue

        # 2. API orqali obuna tekshiruvi
        try:
            member = await bot.get_chat_member(ch.channel_id, user_id)
            if member.status not in ("left", "kicked"):
                continue  # Obuna tasdiqlandi ✓
        except Exception:
            pass  # Tekshirib bo'lmadi (private kanal)

        result.append(ch)
    return result
