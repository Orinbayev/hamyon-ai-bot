"""
Start & Onboarding handler.

Flow for NEW user:
  /start → welcome animation → ask name (FSM) → name saved → main menu

Flow for EXISTING user:
  /start → welcome back + streak info → main menu
"""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.reply import main_menu
from app.bot.states.onboarding import OnboardingState
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.utils.formatters import SEP
from app.utils.motivational import get_message, get_level_info

logger = logging.getLogger("bot.start")
router = Router(name="start")

WELCOME_TEXT = (
    "💼 <b>Assalomu alaykum!</b>\n\n"
    "Men sizning shaxsiy AI moliya yordamchingizman.\n\n"
    "Pul oqimingizni kuzataman,\n"
    "xarajatlaringizni hisoblayman\n"
    "va moliyaviy intizomni oshirishga\n"
    "yordam beraman. 🚀\n\n"
    f"{SEP}\n"
    "Har bir so'm hisobda bo'lishi kerak.\n"
    "Bu mening asosiy prinsipim."
)

ASK_NAME_TEXT = (
    "✨ <b>Sizga qanday murojaat qilishim mumkin?</b>\n\n"
    "Ismingizni yozing 👇"
)


@router.message(Command("start"))
async def cmd_start(
    message: Message,
    user: User,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    await state.clear()

    if not user.custom_name:
        # New user — full onboarding
        await message.answer(WELCOME_TEXT, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
        await message.answer(ASK_NAME_TEXT, parse_mode="HTML")
        await state.set_state(OnboardingState.waiting_for_name)
    else:
        # Returning user — premium welcome back
        name = user.display_name
        icon, level_name = get_level_info(user.level)
        streak_line = (
            f"\n🔥 Streak: <b>{user.streak_days} kun</b>" if user.streak_days >= 3 else ""
        )
        level_line = f"\n{icon} <b>{level_name}</b>" if user.level >= 2 else ""

        await message.answer(
            f"👋 Xush kelibsiz qaytib, <b>{name}</b>!\n"
            f"{level_line}{streak_line}\n\n"
            f"{get_message('welcome_back', name)}",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )


@router.message(OnboardingState.waiting_for_name)
async def handle_onboarding_name(
    message: Message,
    user: User,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    raw = message.text.strip() if message.text else ""

    if not raw or len(raw) > 50:
        await message.answer(
            "⚠️ Iltimos, to'g'ri ism kiriting (1–50 harf).\n\nMisol: <i>Amirxon</i>",
            parse_mode="HTML",
        )
        return

    # Only letters, spaces, apostrophes allowed
    if any(c for c in raw if not (c.isalpha() or c in " '-")):
        await message.answer(
            "⚠️ Ismda faqat harflar bo'lishi kerak.\n\nMisol: <i>Amirxon</i>",
            parse_mode="HTML",
        )
        return

    repo = UserRepository(session)
    await repo.set_custom_name(user, raw)
    await state.clear()

    icon, level_name = get_level_info(1)

    await message.answer(
        f"✅ <b>Ajoyib, {raw}!</b>\n\n"
        f"Siz endi moliyaviy nazorat yo'lida\n"
        f"birinchi qadamni qo'ydingiz. 🚀\n\n"
        f"{SEP}\n"
        f"{icon} Boshlang'ich daraja: <b>{level_name}</b>\n\n"
        f"🎯 Birinchi xarajat yoki kirimni\n"
        f"oddiy gapda yozing:\n\n"
        f"  <i>Taxi 20 ming</i>\n"
        f"  <i>Maosh 3 million kirim</i>\n\n"
        f"Tayyor! 💪",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, user: User) -> None:
    name = user.display_name
    await message.answer(
        f"<b>Qanday ishlatish, {name}?</b>\n\n"
        f"Shunchaki matn yoki 🎤 ovoz yuboring:\n\n"
        f"  <i>Ovqatga 45 ming ketdi</i>\n"
        f"  <i>Taxi 20 000</i>\n"
        f"  <i>Maosh 5 million tushdi</i>\n\n"
        f"{SEP}\n"
        f"📊 <b>Tugmalar</b>\n\n"
        f"📅 Bugun — bugungi hisobot\n"
        f"📆 Hafta — haftalik hisobot\n"
        f"🗓 Oy — oylik hisobot\n"
        f"💰 Balans — umumiy holat\n"
        f"📊 Kategoriyalar — xarajat taqsimoti\n"
        f"📋 Tarix — oxirgi yozuvlar\n"
        f"📤 Eksport — Excel / CSV\n\n"
        f"{SEP}\n"
        f"✏️ <b>Boshqarish</b>\n\n"
        f"/delete — oxirgi yozuvni o'chirish\n"
        f"/delete 42 — #42 raqamli yozuvni o'chirish\n"
        f"/clear — barcha tarixni tozalash",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )
