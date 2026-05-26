"""
Bot buyruqlari: /today, /week, /month, /balance, /categories,
/history, /delete, /export
"""

import logging
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from apps.transactions.models import Transaction
from apps.users.models import TelegramUser
from bot.keyboards.inline import (
    clear_after_export_keyboard,
    clear_confirm_keyboard,
    delete_confirm_keyboard,
    export_format_keyboard,
    export_period_keyboard,
    tx_delete_confirm_keyboard,
)
from services import export as export_service
from services import reports

logger = logging.getLogger("bot")
router = Router(name="commands")

SEP = "━" * 15


# ── Hisobot buyruqlari ───────────────────────────────────────────────────────

@router.message(Command("today"))
async def cmd_today(message: Message, db_user: TelegramUser):
    text = await reports.build_today_report(db_user)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("week"))
async def cmd_week(message: Message, db_user: TelegramUser):
    text = await reports.build_week_report(db_user)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("month"))
async def cmd_month(message: Message, db_user: TelegramUser):
    text = await reports.build_month_report(db_user)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("balance"))
async def cmd_balance(message: Message, db_user: TelegramUser):
    text = await reports.build_balance_report(db_user)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("categories"))
async def cmd_categories(message: Message, db_user: TelegramUser):
    text = await reports.build_categories_report(db_user)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("history"))
async def cmd_history(message: Message, db_user: TelegramUser):
    text = await reports.build_history(db_user, limit=20)
    await message.answer(text, parse_mode="HTML")


# ── /delete ──────────────────────────────────────────────────────────────────

@router.message(Command("delete"))
async def cmd_delete(message: Message, db_user: TelegramUser):
    args = message.text.split(maxsplit=1)

    if len(args) > 1 and args[1].isdigit():
        tx_id = int(args[1])
        tx = await Transaction.objects.filter(id=tx_id, user=db_user).select_related("category").afirst()
        if not tx:
            await message.answer(f"❌ #{tx_id} ID li yozuv topilmadi.")
            return
    else:
        tx = await Transaction.objects.filter(user=db_user).order_by("-created_at").select_related("category").afirst()
        if not tx:
            await message.answer("❌ Hali hech narsa yozilmagan.")
            return

    type_label = "💰 Kirim" if tx.type == "income" else "💸 Chiqim"
    cat_name = tx.category.name if tx.category else "Boshqa"
    amount_str = f"{float(tx.amount):,.0f}".replace(",", " ") + f" {tx.currency}"

    lines = [
        "🗑 <b>O'chirish tasdiqlovi</b>",
        "",
        f"<code>#{tx.id}</code> — {cat_name}",
        f"{type_label}:  {amount_str}",
        f"📅 {tx.transaction_date.strftime('%d.%m.%Y')}",
    ]
    if tx.note:
        lines.append(f"📝 {tx.note}")
    lines += ["", "O'chirishni tasdiqlaysizmi?"]

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=delete_confirm_keyboard(tx.id),
    )


@router.callback_query(F.data.startswith("delete_confirm:"))
async def delete_confirm(callback: CallbackQuery, db_user: TelegramUser):
    tx_id = int(callback.data.split(":")[1])
    deleted, _ = await Transaction.objects.filter(id=tx_id, user=db_user).adelete()
    if deleted:
        await callback.message.edit_text(f"✅ #{tx_id} muvaffaqiyatli o'chirildi.")
    else:
        await callback.message.edit_text("❌ Yozuv topilmadi yoki allaqachon o'chirilgan.")
    await callback.answer()


@router.callback_query(F.data == "delete_cancel")
async def delete_cancel(callback: CallbackQuery):
    await callback.message.edit_text("↩️ Bekor qilindi.")
    await callback.answer()


# ── Tarix inline o'chirish ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("tx:del:"))
async def tx_delete_ask(callback: CallbackQuery, db_user: TelegramUser):
    tx_id = int(callback.data.split(":")[2])
    tx = await Transaction.objects.filter(id=tx_id, user=db_user).select_related("category").afirst()
    if not tx:
        await callback.answer("❌ Yozuv topilmadi.", show_alert=True)
        return

    type_label = "💰 Kirim" if tx.type == "income" else "💸 Chiqim"
    cat_name = tx.category.name if tx.category else "Boshqa"
    amount_str = f"{float(tx.amount):,.0f}".replace(",", " ") + f" {tx.currency}"

    text = (
        f"🗑 <b>O'chirishni tasdiqlang</b>\n\n"
        f"<code>#{tx.id}</code> — {cat_name}\n"
        f"{type_label}:  {amount_str}\n"
        f"📅 {tx.transaction_date.strftime('%d.%m.%Y')}"
    )
    if tx.note:
        text += f"\n📝 {tx.note}"

    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=tx_delete_confirm_keyboard(tx_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tx:del_ok:"))
async def tx_delete_confirm_cb(callback: CallbackQuery, db_user: TelegramUser):
    tx_id = int(callback.data.split(":")[2])
    deleted, _ = await Transaction.objects.filter(id=tx_id, user=db_user).adelete()
    await callback.answer("✅ O'chirildi!" if deleted else "❌ Topilmadi.", show_alert=False)

    text = await reports.build_history(db_user, limit=20)
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data == "tx:del_no")
async def tx_delete_cancel(callback: CallbackQuery, db_user: TelegramUser):
    text = await reports.build_history(db_user, limit=20)
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


# ── /clear ───────────────────────────────────────────────────────────────────

@router.message(Command("clear"))
async def cmd_clear(message: Message, db_user: TelegramUser):
    count = await Transaction.objects.filter(user=db_user).acount()
    if count == 0:
        await message.answer("📭 Tarixda hech narsa yo'q. Tozalash shart emas.")
        return

    await message.answer(
        f"⚠️ <b>Barcha tarixni tozalash</b>\n"
        f"{SEP}\n"
        f"Sizda <b>{count} ta</b> tranzaksiya mavjud.\n\n"
        f"Barcha yozuvlar butunlay o'chiriladi\n"
        f"va tiklash imkoni bo'lmaydi.\n\n"
        f"Tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=clear_confirm_keyboard(),
    )


@router.callback_query(F.data == "clear_export")
async def clear_export_cb(callback: CallbackQuery, db_user: TelegramUser):
    await callback.answer("⏳ Excel tayyorlanmoqda...")
    try:
        file_bytes = await export_service.export_excel(db_user)
        today = date.today()
        doc = BufferedInputFile(file_bytes.read(), filename=f"harajat_{today}.xlsx")
        await callback.message.answer_document(
            doc,
            caption=f"📊 <b>Barcha tarix eksport qilindi</b>\n{SEP}\nEndi tozalashni davom ettirasizmi?",
            parse_mode="HTML",
            reply_markup=clear_after_export_keyboard(),
        )
        await callback.message.delete()
    except Exception as e:
        logger.exception("Clear export xatosi: %s", e)
        await callback.message.edit_text(
            "❌ Eksport qilishda xato. Shunday tozalaysizmi?",
            reply_markup=clear_after_export_keyboard(),
        )


async def _edit_message(callback: CallbackQuery, text: str, **kwargs) -> None:
    """edit_text for normal messages, edit_caption for media (document, photo)."""
    msg = callback.message
    if msg.text:
        await msg.edit_text(text, **kwargs)
    else:
        await msg.edit_caption(caption=text, **kwargs)


@router.callback_query(F.data == "clear_confirm")
async def clear_confirm_cb(callback: CallbackQuery, db_user: TelegramUser):
    deleted, _ = await Transaction.objects.filter(user=db_user).adelete()
    await _edit_message(
        callback,
        f"✅ <b>Tarix tozalandi</b>\n{SEP}\n{deleted} ta yozuv o'chirildi.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "clear_cancel")
async def clear_cancel_cb(callback: CallbackQuery):
    await _edit_message(callback, "↩️ Bekor qilindi.")
    await callback.answer()


# ── /export ──────────────────────────────────────────────────────────────────

@router.message(Command("export"))
async def cmd_export(message: Message):
    await message.answer(
        "📤 <b>Eksport</b>\n\nFayl formatini tanlang:",
        parse_mode="HTML",
        reply_markup=export_format_keyboard(),
    )


@router.callback_query(F.data.startswith("export:"))
async def export_format_chosen(callback: CallbackQuery):
    fmt = callback.data.split(":")[1]
    if fmt == "cancel":
        await callback.message.edit_text("❌ Bekor qilindi.")
        await callback.answer()
        return
    await callback.message.edit_text(
        "📅 <b>Qaysi davr uchun eksport?</b>",
        parse_mode="HTML",
        reply_markup=export_period_keyboard(fmt),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("export_period:"))
async def export_period_chosen(callback: CallbackQuery, db_user: TelegramUser):
    _, fmt, period = callback.data.split(":")

    today = date.today()
    start = end = None
    if period == "today":
        start = end = today
        label = "Bugun"
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        end = today
        label = "Bu hafta"
    elif period == "month":
        start = today.replace(day=1)
        end = today
        label = "Bu oy"
    else:
        label = "Barcha vaqt"

    await callback.message.edit_text("⏳ Fayl tayyorlanmoqda...")

    try:
        if fmt == "excel":
            file_bytes = await export_service.export_excel(db_user, start, end)
            filename = f"harajat_{today}.xlsx"
        else:
            file_bytes = await export_service.export_csv(db_user, start, end)
            filename = f"harajat_{today}.csv"

        doc = BufferedInputFile(file_bytes.read(), filename=filename)
        await callback.message.delete()
        await callback.message.answer_document(
            doc,
            caption=f"📊 <b>{label}</b> — {today.strftime('%d.%m.%Y')}",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception("Export xatosi: %s", e)
        await callback.message.edit_text("❌ Eksport qilishda xato yuz berdi.")

    await callback.answer()
