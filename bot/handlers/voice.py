"""
Ovozli xabarlarni qayta ishlash.
"""

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from apps.users.models import TelegramUser
from bot.handlers.message import SEP, _build_preview, _build_success_reply, _save_transactions, _LAST_TX
from bot.keyboards.inline import confirm_transactions_keyboard, tx_quick_actions_keyboard
from services import gemini, voice as voice_service

logger = logging.getLogger("bot")
router = Router(name="voice")

VOICE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.message(F.voice)
async def handle_voice(message: Message, db_user: TelegramUser, state: FSMContext):
    # Fayl hajmini tekshirish
    if message.voice.file_size and message.voice.file_size > VOICE_MAX_BYTES:
        await message.answer(
            "⚠️ Ovoz fayli juda katta (maksimum 10MB).\n"
            "Iltimos qisqaroq ovoz yuboring yoki matn orqali yozing."
        )
        return

    thinking_msg = await message.answer("🎤 Ovoz tahlil qilinmoqda...")

    try:
        audio_bytes, mime_type = await voice_service.download_voice(message.bot, message.voice)
        items, transcription = await gemini.parse_voice(audio_bytes, mime_type)
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
        if transcription:
            await message.answer(
                f"⚠️ <b>Tranzaksiya topilmadi</b>\n\n"
                f"Men shunday eshitdim:\n"
                f"<i>«{transcription}»</i>\n\n"
                f"Agar noto'g'ri bo'lsa, matn orqali yozing:\n"
                f"<code>Ovqatga 45 ming</code>",
                parse_mode="HTML",
            )
        else:
            await message.answer(
                "⚠️ <b>Ovoz tushunilmadi</b>\n\n"
                "Shovqin juda kuchli bo'lishi mumkin. Matn orqali yozing:\n"
                "<code>Ovqatga 45 ming</code>",
                parse_mode="HTML",
            )
        return

    raw_text = f"[voice] {message.voice.file_id}"

    if len(items) == 1:
        saved = await _save_transactions(db_user, items, raw_text)
        if saved:
            _LAST_TX[db_user.telegram_id] = [tx.id for tx in saved]
        reply = await _build_success_reply(db_user, items, saved)
        kb = tx_quick_actions_keyboard(saved[0].id) if saved else None
        await message.answer(reply, parse_mode="HTML", reply_markup=kb)
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
