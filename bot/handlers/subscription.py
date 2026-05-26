"""
Subscription handlers:
  sub:visit:{id} — kanal tugmasi bosilganda URL tugma ko'rsatadi
  sub:check      — zayafka/obuna tasdiqlanganmi tekshiradi
"""

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from apps.users.models import RequiredChannel, TelegramUser
from bot.middlewares.subscription import (
    SUB_CHECK_CB,
    SUB_VISIT_CB,
    _ZAYAFKA_DONE,
    _channels_still_blocking,
    _channels_to_show,
    _sub_keyboard,
    set_pass_cache,
)

logger = logging.getLogger("bot")
router = Router(name="subscription")


@router.callback_query(F.data.startswith(f"{SUB_VISIT_CB}:"))
async def sub_visit(callback: CallbackQuery, db_user: TelegramUser) -> None:
    """
    Kanal tugmasi bosilganda:
    - Pastda URL tugma paydo bo'ladi (kanalga o'tish uchun)
    - Keyin kanaldan xabar forward qilinsa bot taniydi
    """
    try:
        ch_db_id = int(callback.data.split(":")[2])
        ch = await RequiredChannel.objects.aget(id=ch_db_id)
    except (ValueError, RequiredChannel.DoesNotExist):
        await callback.answer("❌ Kanal topilmadi.", show_alert=True)
        return

    user_id = callback.from_user.id
    bot: Bot = callback.bot

    to_show = await _channels_to_show(bot, user_id)
    done = _ZAYAFKA_DONE.get(user_id, set())

    try:
        await callback.message.edit_reply_markup(
            reply_markup=_sub_keyboard(to_show, done=done, open_ch=ch)
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
    - Obuna API orqali tasdiqlanganmi?
    - Yoki zayafka yuborilganmi?
    Ikkalasidan biri bo'lsa — ruxsat.
    """
    bot: Bot = callback.bot
    user_id = callback.from_user.id

    still_blocking = await _channels_still_blocking(bot, user_id)

    if not still_blocking:
        set_pass_cache(user_id)
        await callback.answer("✅ Botdan foydalanishingiz mumkin!", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    # Hali bloklashda — nima qilish kerakligini ko'rsat
    names = ", ".join(ch.title for ch in still_blocking)
    await callback.answer(
        f"⚠️ Quyidagi kanal(lar) tasdiqlanmadi:\n{names}\n\n"
        "Kanalga o'ting va xabar forward qiling!",
        show_alert=True,
    )
    done = _ZAYAFKA_DONE.get(user_id, set())
    try:
        await callback.message.edit_reply_markup(
            reply_markup=_sub_keyboard(still_blocking, done=done)
        )
    except Exception:
        pass
