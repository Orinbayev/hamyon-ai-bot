"""
Subscription handlers:
  sub:visit:{id} — kanal tugmasi bosildi: zayafka belgilash + URL ko'rsatish
  sub:check      — barcha tugmalar bosilganmi tekshirish
"""

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from apps.users.models import RequiredChannel, TelegramUser
from bot.middlewares.subscription import (
    SUB_CHECK_CB,
    SUB_VISIT_CB,
    _VISITED,
    _load_active_channels,
    _sub_keyboard,
    has_visited_all,
    mark_visited,
    set_pass_cache,
)

logger = logging.getLogger("bot")
router = Router(name="subscription")


@router.callback_query(F.data.startswith(f"{SUB_VISIT_CB}:"))
async def sub_visit(callback: CallbackQuery, db_user: TelegramUser) -> None:
    """
    Kanal tugmasi bosildi:
    - Zayafka belgilanadi (bosildi deb)
    - Klaviaturada ✅ ko'rinadi
    - URL tugma chiqadi (kanalga o'tish uchun)
    """
    try:
        ch_db_id = int(callback.data.split(":")[2])
        ch = await RequiredChannel.objects.aget(id=ch_db_id)
    except (ValueError, RequiredChannel.DoesNotExist):
        await callback.answer("❌ Kanal topilmadi.", show_alert=True)
        return

    user_id = callback.from_user.id

    # Bosilganini belgilash
    mark_visited(user_id, ch_db_id)

    # Klaviaturani yangilash: ✅ belgi + URL tugma
    channels = await _load_active_channels()
    visited = _VISITED.get(user_id, set())
    try:
        await callback.message.edit_reply_markup(
            reply_markup=_sub_keyboard(channels, visited=visited, open_ch=ch)
        )
    except Exception:
        pass

    if not ch.link:
        await callback.answer(
            "⚠️ Kanal havolasi yo'q. Admin invite link qo'shishi kerak.",
            show_alert=True,
        )
    else:
        await callback.answer()


@router.callback_query(F.data == SUB_CHECK_CB)
async def sub_check(callback: CallbackQuery, db_user: TelegramUser) -> None:
    """
    Tekshirish:
    - Barcha kanal tugmalari bosilganmi?
    - Ha → botdan foydalanishga ruxsat
    - Yo'q → xato xabari
    """
    user_id = callback.from_user.id
    channels = await _load_active_channels()

    if not channels:
        # Hech qanday majburiy kanal yo'q → o'tkazib yuborish
        set_pass_cache(user_id)
        await callback.answer("✅ Botdan foydalanishingiz mumkin!", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    if not has_visited_all(user_id, channels):
        # Qaysi kanallar bosilmagan
        visited = _VISITED.get(user_id, set())
        not_visited_count = sum(1 for ch in channels if ch.id not in visited)
        await callback.answer(
            f"⚠️ Hali {not_visited_count} ta kanal tugmasi bosilmadi!\n"
            "Avval barcha kanal tugmalarini bosing.",
            show_alert=True,
        )
        return

    # Hammasi bosilgan → ruxsat berish
    set_pass_cache(user_id)
    await callback.answer("✅ Botdan foydalanishingiz mumkin!", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass
