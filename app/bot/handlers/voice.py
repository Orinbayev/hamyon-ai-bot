import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.parser import AIParser
from app.bot.handlers.message import _build_reply, _make_services, _preview
from app.bot.keyboards.inline import confirm_transactions_keyboard
from app.bot.keyboards.reply import main_menu
from app.models.user import User
from app.utils.formatters import SEP

logger = logging.getLogger("bot.voice")
router = Router(name="voice")


async def _download_voice(bot, voice) -> tuple[bytes, str]:
    file = await bot.get_file(voice.file_id)
    bio = await bot.download_file(file.file_path)
    return bio.read(), "audio/ogg"


@router.message(F.voice)
async def handle_voice(
    message: Message,
    user: User,
    user_id: int,
    session: AsyncSession,
    state: FSMContext,
    ai_parser: AIParser,
) -> None:
    name = user.display_name
    thinking = await message.answer("🎤 Ovoz tahlil qilinmoqda...")

    try:
        audio_bytes, mime_type = await _download_voice(message.bot, message.voice)
        items = await ai_parser.parse_voice(audio_bytes, mime_type)
    except Exception as e:
        logger.exception("Voice xatosi: %s", e)
        await thinking.delete()
        await message.answer(
            f"❌ Ovozni qayta ishlashda xato yuz berdi, {name}\n\n"
            "Iltimos matn orqali yuboring.",
            parse_mode="HTML",
        )
        return

    await thinking.delete()

    if not items:
        await message.answer(
            f"⚠️ Ovozda moliyaviy ma'lumot topilmadi, {name}\n\n"
            "Aniqroq ayting, masalan:\n"
            "<i>\"Ovqatga qirq besh ming so'm ketdi\"</i>",
            parse_mode="HTML",
        )
        return

    raw_text = f"[voice] {message.voice.file_id}"
    tx_svc, eng_svc = _make_services(session)
    context = "save_income" if all(i.type == "income" for i in items) else "save_expense"

    if len(items) == 1:
        saved = await tx_svc.save_from_ai(user_id, items, raw_text)
        engagement = await eng_svc.record_activity(user, context=context, count=len(saved))
        reply = await _build_reply(user, items, saved, engagement, session)
        await message.answer(reply, parse_mode="HTML", reply_markup=main_menu())
        return

    await state.update_data(
        pending_items=[i.model_dump(mode="json") for i in items],
        raw_text=raw_text,
    )
    await message.answer(
        f"🎤 <b>Ovozdan {len(items)} ta tranzaksiya topildi, {name}:</b>\n\n"
        f"{_preview(items)}\n\n{SEP}\n"
        "Hammasini saqlashni tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=confirm_transactions_keyboard(len(items)),
    )
