"""
Ovozli xabarlarni qayta ishlash.
"""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from apps.users.models import TelegramUser
from bot.handlers.message import SEP, _build_preview, _build_success_reply, _save_transactions
from bot.keyboards.inline import confirm_transactions_keyboard
from services import gemini, voice as voice_service

logger = logging.getLogger("bot")
router = Router(name="voice")


@router.message(F.voice)
async def handle_voice(message: Message, db_user: TelegramUser, state: FSMContext):
    thinking_msg = await message.answer("🎤 Ovoz tahlil qilinmoqda...")

    try:
        audio_bytes, mime_type = await voice_service.download_voice(message.bot, message.voice)
        items = await gemini.parse_voice(audio_bytes, mime_type)
    except Exception as e:
        logger.exception("Voice processing xatosi: %s", e)
        await thinking_msg.delete()
        await message.answer(
            "❌ Ovozni qayta ishlashda xato yuz berdi\n\n"
            "Iltimos matn orqali yuboring yoki qayta urinib ko'ring.",
            parse_mode="HTML",
        )
        return

    await thinking_msg.delete()

    if not items:
        await message.answer(
            "⚠️ Ovozda moliyaviy ma'lumot topilmadi\n\n"
            "Aniqroq ayting, masalan:\n"
            "<i>\"Ovqatga qirq besh ming so'm ketdi\"</i>",
            parse_mode="HTML",
        )
        return

    raw_text = f"[voice] {message.voice.file_id}"

    if len(items) == 1:
        saved = await _save_transactions(db_user, items, raw_text)
        reply = await _build_success_reply(db_user, items, saved)
        await message.answer(reply, parse_mode="HTML")
        return

    preview = _build_preview(items)
    await state.update_data(pending_items=items, raw_text=raw_text)

    await message.answer(
        f"🎤 <b>Ovozdan {len(items)} ta tranzaksiya topildi:</b>\n\n"
        f"{preview}\n\n"
        f"{SEP}\n"
        "Hammasini saqlashni tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=confirm_transactions_keyboard(len(items)),
    )
