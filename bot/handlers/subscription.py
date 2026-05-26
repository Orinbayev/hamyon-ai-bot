"""
Subscription handlers:
  sub:visit:{id} — kanalga o'tish + bosilganini belgilash
  sub:check      — tekshirish (faqat visit bosilgandan keyin ishlaydi)
"""

import logging

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery

from apps.users.models import RequiredChannel, TelegramUser
from bot.middlewares.subscription import (
    SUB_CHECK_CB,
    SUB_VISIT_CB,
    _channels_strictly_blocking,
    _channels_to_show,
    _sub_keyboard,
    _sub_text,
    has_visited_any,
    mark_visited,
    set_pass_cache,
)

logger = logging.getLogger("bot")
router = Router(name="subscription")


@router.callback_query(F.data.startswith(f"{SUB_VISIT_CB}:"))
async def sub_visit(callback: CallbackQuery, db_user: TelegramUser) -> None:
    """Kanal tugmasi bosilganda: kanalga o'tkazadi + "bosildi" belgilaydi."""
    try:
        ch_db_id = int(callback.data.split(":")[2])
        ch = await RequiredChannel.objects.aget(id=ch_db_id)
    except (ValueError, RequiredChannel.DoesNotExist):
        await callback.answer("❌ Kanal topilmadi.", show_alert=True)
        return

    mark_visited(callback.from_user.id, ch_db_id)

    # Kanalga yo'naltirish (URL tugma bilan bir xil natija, lekin trackingga mumkin)
    await callback.answer(url=ch.link)


@router.callback_query(F.data == SUB_CHECK_CB)
async def sub_check(callback: CallbackQuery, db_user: TelegramUser) -> None:
    """
    Tekshirish:
      1. Avval kamida bitta "Zayafka yuborish" bosilganligini tekshiradi
      2. Keyin public kanallar uchun aniq obuna tekshiruvi
    """
    bot: Bot = callback.bot
    user_id = callback.from_user.id

    # Avval ko'rsatiladigan kanallarni olish (qaysilar hali to'siq?)
    to_show = await _channels_to_show(bot, user_id)

    if not to_show:
        # Hamma kanalga a'zo bo'lgan
        set_pass_cache(user_id)
        await callback.answer("✅ Botdan foydalanishingiz mumkin!", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    # Kamida bitta "Zayafka yuborish" bosilganmi?
    if not has_visited_any(user_id, to_show):
        await callback.answer(
            "⚠️ Avval «Zayafka yuborish» tugmasini bosing!",
            show_alert=True,
        )
        return

    # Visit bosilgan — endi aniq tekshiruv (public / bot admin kanallar)
    still_blocking = await _channels_strictly_blocking(bot, user_id)

    if still_blocking:
        # Public kanal(lar)ga hali a'zo bo'lmagan
        await callback.answer("⚠️ Hali obuna bo'lmadingiz!", show_alert=True)
        try:
            await callback.message.edit_reply_markup(
                reply_markup=_sub_keyboard(still_blocking)
            )
        except Exception:
            pass
        return

    # Barcha tekshiruvlar o'tdi → o'tkazib yuborish
    set_pass_cache(user_id)
    await callback.answer("✅ Botdan foydalanishingiz mumkin!", show_alert=True)
    try:
        await callback.message.delete()
    except Exception:
        pass
