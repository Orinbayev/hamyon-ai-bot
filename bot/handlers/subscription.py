"""
Majburiy obuna tekshirish handler.
"✅ Tekshirish" tugmasi bosilganda ishlaydi.
"""

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from apps.users.models import TelegramUser
from bot.middlewares.subscription import (
    SUB_CHECK_CB,
    _channels_blocking,
    _channels_to_show,
    _sub_keyboard,
    _sub_text,
    set_pass_cache,
)

logger = logging.getLogger("bot")
router = Router(name="subscription")


@router.callback_query(F.data == SUB_CHECK_CB)
async def sub_check(callback: CallbackQuery, db_user: TelegramUser) -> None:
    bot: Bot = callback.bot
    user_id = callback.from_user.id

    # Faqat aniq tekshirib bo'ladigan (public / bot admin) kanallarni ko'rib chiqamiz
    still_blocked = await _channels_blocking(bot, user_id)

    if not still_blocked:
        # Barcha aniq tekshiruv o'tdi → o'tkaz + qisqa cache
        set_pass_cache(user_id)
        await callback.answer("✅ Botdan foydalanishingiz mumkin!", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    # Aniq tekshirib bo'ladigan kanal(lar)ga hali obuna bo'lmagan
    await callback.answer("⚠️ Hali obuna bo'lmadingiz!", show_alert=True)
    try:
        # Faqat blocklayotgan kanallarni ko'rsat
        await callback.message.edit_reply_markup(
            reply_markup=_sub_keyboard(still_blocked)
        )
    except Exception:
        try:
            await callback.message.edit_text(
                _sub_text(len(still_blocked)),
                reply_markup=_sub_keyboard(still_blocked),
            )
        except Exception:
            pass
