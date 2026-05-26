"""
Reply keyboard tugmalarini qayta ishlash.
"""

import logging

from aiogram import F, Router
from aiogram.types import Message

from apps.users.models import TelegramUser
from apps.transactions.models import Transaction
from bot.keyboards.inline import clear_confirm_keyboard, export_format_keyboard, history_delete_keyboard
from bot.keyboards.reply import main_menu
from services import reports
from services.reports import build_history_with_txs

logger = logging.getLogger("bot")
router = Router(name="menu")

LINE = "─" * 28


async def _send_report(message: Message, text: str):
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu())


@router.message(F.text == "📅 Bugun")
async def menu_today(message: Message, db_user: TelegramUser):
    text = await reports.build_today_report(db_user)
    await _send_report(message, text)


@router.message(F.text == "📆 Hafta")
async def menu_week(message: Message, db_user: TelegramUser):
    text = await reports.build_week_report(db_user)
    await _send_report(message, text)


@router.message(F.text == "🗓 Oy")
async def menu_month(message: Message, db_user: TelegramUser):
    text = await reports.build_month_report(db_user)
    await _send_report(message, text)


@router.message(F.text == "💰 Balans")
async def menu_balance(message: Message, db_user: TelegramUser):
    text = await reports.build_balance_report(db_user)
    await _send_report(message, text)


@router.message(F.text == "📊 Kategoriyalar")
async def menu_categories(message: Message, db_user: TelegramUser):
    text = await reports.build_categories_report(db_user)
    await _send_report(message, text)


@router.message(F.text == "📋 Tarix")
async def menu_history(message: Message, db_user: TelegramUser):
    text, txs = await build_history_with_txs(db_user, limit=20)
    kb = history_delete_keyboard(txs) if txs else None
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.message(F.text == "📤 Eksport")
async def menu_export(message: Message):
    await message.answer(
        f"📤 <b>Eksport</b>\n{LINE}\nQaysi formatda yuklamoqchisiz?",
        parse_mode="HTML",
        reply_markup=export_format_keyboard(),
    )


SEP = "━" * 15


@router.message(F.text == "🗑 Tozalash")
async def menu_clear(message: Message, db_user: TelegramUser):
    count = await Transaction.objects.filter(user=db_user).acount()
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
