"""
Subscription handlers:
  sub:visit:{id}   — kanal tugmasi bosildi: URL + "Zayafka yubordim" ko'rsatish
  sub:confirm:{id} — foydalanuvchi zayafka yuborganini tasdiqladi
  sub:check        — barcha kanallar tekshiriladi
  chat_join_request — (bonus) bot admin bo'lsa avtomatik tasdiq
"""

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, ChatJoinRequest

from apps.users.models import RequiredChannel, TelegramUser
from bot.middlewares.subscription import (
    SUB_CHECK_CB,
    SUB_CONFIRM_CB,
    SUB_VISIT_CB,
    _SUB_MESSAGES,
    _VISITED,
    _get_channel_by_tg_id,
    _load_active_channels,
    _save_subscription_verified,
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
    - URL tugma ko'rsatiladi (kanalga o'tish uchun)
    - "✅ Zayafka yubordim" tugmasi paydo bo'ladi
    - Hali zayafka tasdiqlanmagan (faqat confirm orqali belgilanadi)
    """
    try:
        ch_db_id = int(callback.data.split(":")[2])
        ch = await RequiredChannel.objects.aget(id=ch_db_id)
    except (ValueError, RequiredChannel.DoesNotExist):
        await callback.answer("❌ Kanal topilmadi.", show_alert=True)
        return

    user_id = callback.from_user.id
    channels = await _load_active_channels()
    visited = _VISITED.get(user_id, set())

    # URL + "Zayafka yubordim" tugmasini ko'rsatish — hali mark_visited emas
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


@router.callback_query(F.data.startswith(f"{SUB_CONFIRM_CB}:"))
async def sub_confirm(callback: CallbackQuery, db_user: TelegramUser) -> None:
    """
    "✅ Zayafka yubordim" bosildi — foydalanuvchi kanalga zayafka yubordi deb qayd etiladi.
    """
    try:
        ch_db_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Xato.", show_alert=True)
        return

    user_id = callback.from_user.id
    mark_visited(user_id, ch_db_id)

    channels = await _load_active_channels()
    visited = _VISITED.get(user_id, set())

    # "Zayafka yubordim" tugmasini olib tashlab ✅ qo'yamiz
    try:
        await callback.message.edit_reply_markup(
            reply_markup=_sub_keyboard(channels, visited=visited)
        )
    except Exception:
        pass

    await callback.answer("✅ Qayd etildi!")


@router.chat_join_request()
async def on_join_request(update: ChatJoinRequest, bot: Bot) -> None:
    """
    Bot kanalda admin bo'lsa, bu event avtomatik keladi.
    Foydalanuvchi "Zayafka yubordim" tugmasini bosmasdan ham tasdiqlanadi.
    """
    user_id = update.from_user.id
    channel_tg_id = update.chat.id

    ch = await _get_channel_by_tg_id(channel_tg_id)
    if not ch:
        return

    mark_visited(user_id, ch.id)
    logger.info("chat_join_request: user=%s kanal=%s", user_id, ch.title)

    # Obuna xabarini yangilash (✅ belgisini qo'shish)
    sub_msg = _SUB_MESSAGES.get(user_id)
    if sub_msg:
        chat_id, msg_id = sub_msg
        channels = await _load_active_channels()
        visited = _VISITED.get(user_id, set())
        try:
            await bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=msg_id,
                reply_markup=_sub_keyboard(channels, visited=visited),
            )
        except Exception:
            pass


@router.callback_query(F.data == SUB_CHECK_CB)
async def sub_check(callback: CallbackQuery, db_user: TelegramUser, bot: Bot) -> None:
    """
    Tekshirish:
    - sub:confirm orqali belgilangan kanallar tekshiriladi
    - Fallback: allaqachon a'zo bo'lganlar uchun get_chat_member
    """
    user_id = callback.from_user.id
    channels = await _load_active_channels()

    if not channels:
        set_pass_cache(user_id)
        await callback.answer("✅ Botdan foydalanishingiz mumkin!", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    # Fallback: confirm qilinmagan kanallarni API orqali tekshirish
    unverified = [ch for ch in channels if ch.id not in _VISITED.get(user_id, set())]
    for ch in unverified:
        try:
            member = await bot.get_chat_member(chat_id=ch.channel_id, user_id=user_id)
            if member.status in ("member", "administrator", "creator"):
                mark_visited(user_id, ch.id)
        except Exception:
            pass

    if not has_visited_all(user_id, channels):
        visited = _VISITED.get(user_id, set())
        not_visited_count = sum(1 for ch in channels if ch.id not in visited)
        await callback.answer(
            f"⚠️ Hali {not_visited_count} ta kanalga zayafka tasdiqlanmadi!\n"
            "Kanal tugmasini bosing → kanalga o'ting → zayafka yuboring → "
            "\"✅ Zayafka yubordim\" tugmasini bosing.",
            show_alert=True,
        )
        return

    set_pass_cache(user_id)
    await _save_subscription_verified(user_id)
    await callback.answer("✅ Botdan foydalanishingiz mumkin!", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass
