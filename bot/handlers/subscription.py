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
    NUMS,
    _check_subscriptions,
    _sub_keyboard,
    _sub_text,
    mark_passed,
)

logger = logging.getLogger("bot")
router = Router(name="subscription")


@router.callback_query(F.data == SUB_CHECK_CB)
async def sub_check(callback: CallbackQuery, db_user: TelegramUser) -> None:
    bot: Bot = callback.bot
    not_subscribed = await _check_subscriptions(bot, callback.from_user.id)

    if not not_subscribed:
        # Hammaga obuna bo'lindi — o'tkazib yuboramiz
        mark_passed(callback.from_user.id)
        await callback.answer("✅ Botdan foydalanishingiz mumkin!", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    # Hali ham obuna bo'lmagan kanallar bor — lekin "Tekshirish" bosildi
    # Foydalanuvchi intentini ko'rsatdi → sessiyada o'tkazib yuboramiz
    mark_passed(callback.from_user.id)
    await callback.answer("✅ Davom etishingiz mumkin!", show_alert=False)
    try:
        await callback.message.delete()
    except Exception:
        pass
