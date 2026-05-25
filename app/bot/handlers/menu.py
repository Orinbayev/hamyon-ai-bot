"""
Menu handlers — Handler → Service → Repository → DB.
"""
import logging

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import clear_confirm_keyboard, export_format_keyboard
from app.bot.keyboards.reply import main_menu
from app.repositories.transaction_repo import TransactionRepository
from app.models.user import User
from app.repositories.transaction_repo import TransactionRepository
from app.services.report_service import ReportService
from app.utils.formatters import SEP
from app.utils.motivational import get_message

logger = logging.getLogger("bot.menu")
router = Router(name="menu")


def _make_report_service(session: AsyncSession) -> ReportService:
    return ReportService(TransactionRepository(session))


@router.message(F.text == "📅 Bugun")
async def menu_today(message: Message, user: User, user_id: int, session: AsyncSession) -> None:
    svc = _make_report_service(session)
    text = get_message("today_report", user.display_name) + "\n\n" + await svc.today(user_id)
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu())


@router.message(F.text == "📆 Hafta")
async def menu_week(message: Message, user: User, user_id: int, session: AsyncSession) -> None:
    svc = _make_report_service(session)
    text = get_message("week_report", user.display_name) + "\n\n" + await svc.week(user_id)
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu())


@router.message(F.text == "🗓 Oy")
async def menu_month(message: Message, user: User, user_id: int, session: AsyncSession) -> None:
    svc = _make_report_service(session)
    text = get_message("month_report", user.display_name) + "\n\n" + await svc.month(user_id)
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu())


@router.message(F.text == "💰 Balans")
async def menu_balance(message: Message, user: User, user_id: int, session: AsyncSession) -> None:
    svc = _make_report_service(session)
    await message.answer(await svc.balance(user_id), parse_mode="HTML", reply_markup=main_menu())


@router.message(F.text == "📊 Kategoriyalar")
async def menu_categories(message: Message, user: User, user_id: int, session: AsyncSession) -> None:
    svc = _make_report_service(session)
    await message.answer(await svc.categories(user_id), parse_mode="HTML", reply_markup=main_menu())


@router.message(F.text == "📋 Tarix")
async def menu_history(message: Message, user: User, user_id: int, session: AsyncSession) -> None:
    svc = _make_report_service(session)
    await message.answer(await svc.history(user_id, limit=20), parse_mode="HTML", reply_markup=main_menu())


@router.message(F.text == "📤 Eksport")
async def menu_export(message: Message) -> None:
    await message.answer(
        f"📤 <b>Eksport</b>\n{SEP}\nFayl formatini tanlang:",
        parse_mode="HTML",
        reply_markup=export_format_keyboard(),
    )


@router.message(F.text == "🗑 Tozalash")
async def menu_clear(message: Message, user_id: int, session: AsyncSession) -> None:
    count = await TransactionRepository(session).count_for_user(user_id)
    if count == 0:
        await message.answer("📭 Tarixda hech narsa yo'q.", reply_markup=main_menu())
        return
    await message.answer(
        f"⚠️ <b>Barcha tarixni tozalash</b>\n{SEP}\n"
        f"Sizda <b>{count} ta</b> tranzaksiya mavjud.\n\n"
        f"Barcha yozuvlar butunlay o'chiriladi va tiklash imkoni bo'lmaydi.\n\n"
        f"Avval Excel ko'rinishida yuklab olishingiz ham mumkin.",
        parse_mode="HTML",
        reply_markup=clear_confirm_keyboard(),
    )
