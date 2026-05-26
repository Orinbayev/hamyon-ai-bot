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
    _check_subscriptions,
    _sub_keyboard,
    _sub_text,
)

logger = logging.getLogger("bot")
router = Router(name="subscription")


@router.callback_query(F.data == SUB_CHECK_CB)
async def sub_check(callback: CallbackQuery, db_user: TelegramUser) -> None:
    bot: Bot = callback.bot
    not_subscribed = await _check_subscriptions(bot, callback.from_user.id)

    if not not_subscribed:
        await callback.answer("✅ Botdan foydalanishingiz mumkin!", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    # Hali obuna bo'lmagan kanallar bor — qayta ko'rsatish
    await callback.answer("⚠️ Hali obuna bo'lmadingiz!", show_alert=True)
    try:
        await callback.message.edit_reply_markup(
            reply_markup=_sub_keyboard(not_subscribed)
        )
    except Exception:
        try:
            await callback.message.edit_text(
                _sub_text(len(not_subscribed)),
                reply_markup=_sub_keyboard(not_subscribed),
            )
        except Exception:
            pass
