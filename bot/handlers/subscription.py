"""
Majburiy obuna tekshirish handler.
"✅ Obuna bo'ldim" tugmasi bosilganda ishlaydi.
"""

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from apps.users.models import TelegramUser
from bot.middlewares.subscription import SUB_CHECK_CB, _check_subscriptions

logger = logging.getLogger("bot")
router = Router(name="subscription")


@router.callback_query(F.data == SUB_CHECK_CB)
async def sub_check(callback: CallbackQuery, db_user: TelegramUser) -> None:
    bot: Bot = callback.bot
    not_subscribed = await _check_subscriptions(bot, callback.from_user.id)

    if not not_subscribed:
        await callback.answer("✅ Rahmat! Botdan foydalanishingiz mumkin.", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    # Hali ham obuna bo'lmagan kanallar bor
    b = InlineKeyboardBuilder()
    for ch in not_subscribed:
        b.row(InlineKeyboardButton(text=f"📡 {ch.title}", url=ch.link))
    b.row(InlineKeyboardButton(text="✅ Tekshirish", callback_data=SUB_CHECK_CB))

    still = "\n".join(f"📡 <b>{ch.title}</b>" for ch in not_subscribed)
    await callback.answer("⚠️ Hali obuna bo'lmagan kanallar bor!", show_alert=True)
    try:
        await callback.message.edit_text(
            "🔒 <b>Majburiy obuna</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            "Quyidagi kanallarga hali obuna bo'lmadingiz:\n\n"
            f"{still}\n\n"
            "Obuna bo'lgach <b>✅ Tekshirish</b> tugmasini bosing.",
            parse_mode="HTML",
            reply_markup=b.as_markup(),
        )
    except Exception:
        pass
