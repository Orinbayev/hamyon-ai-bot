"""
Subscription handlers:
  sub:visit:{id}    — kanal tugmasi bosildi: URL ko'rsatish (zayafka emas)
  sub:check         — zayafkalar tekshiriladi
  chat_join_request — foydalanuvchi kanalga zayafka yubordi (asosiy tasdiq)
"""

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, ChatJoinRequest

from apps.users.models import RequiredChannel, TelegramUser
from bot.middlewares.subscription import (
    SUB_CHECK_CB,
    SUB_VISIT_CB,
    _SUB_MESSAGES,
    _VISITED,
    _get_channel_by_tg_id,
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
    Kanal tugmasi bosildi → faqat URL tugma ko'rsatiladi.
    Zayafka yuborgandan keyin chat_join_request orqali belgilanadi.
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

    # Faqat URL tugma ko'rsatiladi — zayafka yuborilmagan, shuning uchun ✅ qo'yilmaydi
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


@router.chat_join_request()
async def on_join_request(update: ChatJoinRequest, bot: Bot) -> None:
    """
    Foydalanuvchi kanalga zayafka yubordi.
    Bu event bot admin bo'lgan va a'zolik tasdig'i yoqilgan kanallarda ishlaydi.
    """
    user_id = update.from_user.id
    channel_tg_id = update.chat.id

    ch = await _get_channel_by_tg_id(channel_tg_id)
    if not ch:
        return  # Bu bizning majburiy kanalimiz emas

    mark_visited(user_id, ch.id)
    logger.info("Zayafka qabul qilindi: user=%s kanal=%s", user_id, ch.title)

    # Obuna xabari klaviaturasini yangilash (✅ belgi qo'shish)
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
    - chat_join_request orqali belgilangan kanallar
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

    # Fallback: chat_join_request orqali belgilanmagan kanallarni API orqali tekshirish
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
            f"⚠️ Hali {not_visited_count} ta kanalga zayafka yuborilmadi!\n"
            "Avval barcha kanallarga zayafka yuboring.",
            show_alert=True,
        )
        return

    set_pass_cache(user_id)
    await callback.answer("✅ Botdan foydalanishingiz mumkin!", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass
