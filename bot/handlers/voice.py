"""
Ovozli xabarlarni qayta ishlash.
"""

import hashlib
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from apps.users.models import TelegramUser
from bot.handlers.message import SEP, _build_preview, _build_success_reply, _save_transactions, _LAST_TX
from bot.keyboards.inline import confirm_transactions_keyboard, tx_quick_actions_keyboard, voice_retry_keyboard
from services import gemini, voice as voice_service

logger = logging.getLogger("bot")
router = Router(name="voice")

VOICE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

# file_id lar callback_data 64-bayt limitiga sig'maydi — xotirada saqlanadi
_FILE_ID_CACHE: dict[str, str] = {}


def _cache_file_id(file_id: str) -> str:
    """file_id ni 8-belgilik kalit bilan saqlaydi, callbackda ishlatish uchun."""
    key = hashlib.md5(file_id.encode()).hexdigest()[:8]
    _FILE_ID_CACHE[key] = file_id
    return key


async def _process_voice(
    audio_bytes: bytes,
    mime_type: str,
    db_user: TelegramUser,
    file_id: str,
    state: FSMContext,
    reply_to: Message,
):
    """Audio baytlarini tahlil qilib natijani yuboradi."""
    try:
        items, transcription = await gemini.parse_voice(audio_bytes, mime_type)
    except Exception as e:
        err_str = str(e)
        logger.exception("Voice processing xatosi: %s", e)
        if "503" in err_str or "UNAVAILABLE" in err_str:
            key = _cache_file_id(file_id)
            await reply_to.answer(
                "⏳ <b>AI server hozir yuklanib qolgan</b>\n\n"
                "Bu vaqtinchalik holat. Bir necha daqiqadan keyin:\n"
                "• Pastdagi tugmani bosing\n"
                "• Yoki matn orqali yozing: <code>Ovqatga 45 ming</code>",
                parse_mode="HTML",
                reply_markup=voice_retry_keyboard(key),
            )
        else:
            await reply_to.answer(
                "❌ <b>Ovozni tahlil qilishda xato</b>\n\n"
                "Matn orqali yozing:\n"
                "<code>Ovqatga 45 ming</code>",
                parse_mode="HTML",
            )
        return

    if not items:
        if transcription:
            await reply_to.answer(
                f"⚠️ <b>Moliyaviy ma'lumot topilmadi</b>\n\n"
                f"Men shunday eshitdim:\n"
                f"<i>«{transcription}»</i>\n\n"
                f"Matn orqali yozing:\n"
                f"<code>Ovqatga 45 ming</code>",
                parse_mode="HTML",
            )
        else:
            await reply_to.answer(
                "⚠️ <b>Ovoz tushunilmadi</b>\n\n"
                "Shovqin juda kuchli bo'lishi mumkin.\n"
                "Tinchroq joyda qayta yuboring yoki matn orqali yozing:\n"
                "<code>Ovqatga 45 ming</code>",
                parse_mode="HTML",
            )
        return

    raw_text = f"[voice] {file_id}"

    if len(items) == 1:
        saved = await _save_transactions(db_user, items, raw_text)
        if saved:
            _LAST_TX[db_user.telegram_id] = [tx.id for tx in saved]
        reply = await _build_success_reply(db_user, items, saved)
        kb = tx_quick_actions_keyboard(saved[0].id) if saved else None
        await reply_to.answer(reply, parse_mode="HTML", reply_markup=kb)
        return

    preview = _build_preview(items)
    await state.update_data(pending_items=items, raw_text=raw_text)
    await reply_to.answer(
        f"🎤 <b>Ovozdan {len(items)} ta tranzaksiya topildi:</b>\n\n"
        f"{preview}\n\n"
        f"{SEP}\n"
        "Hammasini saqlashni tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=confirm_transactions_keyboard(len(items)),
    )


@router.message(F.voice)
async def handle_voice(message: Message, db_user: TelegramUser, state: FSMContext):
    if message.voice.file_size and message.voice.file_size > VOICE_MAX_BYTES:
        await message.answer(
            "⚠️ Ovoz fayli juda katta (maksimum 10MB).\n"
            "Iltimos qisqaroq ovoz yuboring yoki matn orqali yozing."
        )
        return

    thinking_msg = await message.answer("🎤 Ovoz tahlil qilinmoqda...")
    audio_bytes, mime_type = await voice_service.download_voice(message.bot, message.voice)
    await thinking_msg.delete()
    await _process_voice(audio_bytes, mime_type, db_user, message.voice.file_id, state, message)


@router.callback_query(F.data.startswith("voice:retry:"))
async def voice_retry_cb(callback: CallbackQuery, db_user: TelegramUser, state: FSMContext):
    key = callback.data.split(":", 2)[2]
    file_id = _FILE_ID_CACHE.get(key)
    if not file_id:
        await callback.answer("⚠️ Sessiya tugagan, ovozni qayta yuboring.", show_alert=True)
        return
    await callback.answer("🎤 Qayta urinilmoqda...")
    try:
        thinking_msg = await callback.message.answer("🎤 Ovoz qayta tahlil qilinmoqda...")
        file = await callback.bot.get_file(file_id)
        file_bytes = await callback.bot.download_file(file.file_path)
        audio_bytes = file_bytes.read()
        await thinking_msg.delete()
        await _process_voice(audio_bytes, "audio/ogg", db_user, file_id, state, callback.message)
    except Exception as e:
        logger.exception("Voice retry xatosi: %s", e)
        await callback.message.answer(
            "❌ Qayta urinishda xato. Matn orqali yozing:\n"
            "<code>Ovqatga 45 ming</code>",
            parse_mode="HTML",
        )
