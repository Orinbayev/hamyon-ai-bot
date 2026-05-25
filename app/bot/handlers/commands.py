import logging
from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.inline import (
    clear_after_export_keyboard,
    clear_confirm_keyboard,
    delete_confirm_keyboard,
    export_format_keyboard,
    export_period_keyboard,
)
from app.models.user import User
from app.repositories.category_repo import CategoryRepository
from app.repositories.transaction_repo import TransactionRepository
from app.services.report_service import ReportService
from app.services.transaction_service import TransactionService
from app.utils.formatters import SEP, fmt_amount

logger = logging.getLogger("bot.commands")
router = Router(name="commands")


def _report_svc(session: AsyncSession) -> ReportService:
    return ReportService(TransactionRepository(session))


def _tx_svc(session: AsyncSession) -> TransactionService:
    return TransactionService(TransactionRepository(session), CategoryRepository(session))


# ── Report commands ───────────────────────────────────────────────────────────

@router.message(Command("today"))
async def cmd_today(message: Message, user_id: int, session: AsyncSession) -> None:
    await message.answer(await _report_svc(session).today(user_id), parse_mode="HTML")


@router.message(Command("week"))
async def cmd_week(message: Message, user_id: int, session: AsyncSession) -> None:
    await message.answer(await _report_svc(session).week(user_id), parse_mode="HTML")


@router.message(Command("month"))
async def cmd_month(message: Message, user_id: int, session: AsyncSession) -> None:
    await message.answer(await _report_svc(session).month(user_id), parse_mode="HTML")


@router.message(Command("balance"))
async def cmd_balance(message: Message, user_id: int, session: AsyncSession) -> None:
    await message.answer(await _report_svc(session).balance(user_id), parse_mode="HTML")


@router.message(Command("categories"))
async def cmd_categories(message: Message, user_id: int, session: AsyncSession) -> None:
    await message.answer(await _report_svc(session).categories(user_id), parse_mode="HTML")


@router.message(Command("history"))
async def cmd_history(message: Message, user_id: int, session: AsyncSession) -> None:
    await message.answer(await _report_svc(session).history(user_id), parse_mode="HTML")


# ── /delete ───────────────────────────────────────────────────────────────────

@router.message(Command("delete"))
async def cmd_delete(message: Message, user_id: int, session: AsyncSession) -> None:
    svc = _tx_svc(session)
    args = message.text.split(maxsplit=1)

    if len(args) > 1 and args[1].isdigit():
        tx = await TransactionRepository(session).get_by_id_for_user(int(args[1]), user_id)
        if not tx:
            await message.answer(f"❌ #{args[1]} ID li yozuv topilmadi.")
            return
    else:
        tx = await svc.get_last(user_id)
        if not tx:
            await message.answer("❌ Hali hech narsa yozilmagan.")
            return

    type_label = "💰 Kirim" if tx.type == "income" else "💸 Chiqim"
    cat_name = tx.category.name if tx.category else "Boshqa"
    amount_str = fmt_amount(tx.amount, tx.currency)

    lines = [
        "🗑 <b>O'chirish tasdiqlovi</b>", "",
        f"<code>#{tx.id}</code> — {cat_name}",
        f"{type_label}:  {amount_str}",
        f"📅 {tx.transaction_date.strftime('%d.%m.%Y')}",
    ]
    if tx.note:
        lines.append(f"📝 {tx.note}")
    lines += ["", "O'chirishni tasdiqlaysizmi?"]

    await message.answer(
        "\n".join(lines), parse_mode="HTML",
        reply_markup=delete_confirm_keyboard(tx.id),
    )


@router.callback_query(F.data.startswith("delete_confirm:"))
async def delete_confirm(callback: CallbackQuery, user_id: int, session: AsyncSession) -> None:
    tx_id = int(callback.data.split(":")[1])
    deleted = await _tx_svc(session).delete_by_id(tx_id, user_id)
    text = f"✅ #{tx_id} muvaffaqiyatli o'chirildi." if deleted else "❌ Yozuv topilmadi."
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "delete_cancel")
async def delete_cancel(callback: CallbackQuery) -> None:
    await callback.message.edit_text("↩️ Bekor qilindi.")
    await callback.answer()


# ── /clear ────────────────────────────────────────────────────────────────────

@router.message(Command("clear"))
async def cmd_clear(message: Message, user_id: int, session: AsyncSession) -> None:
    repo = TransactionRepository(session)
    count = await repo.count_for_user(user_id)
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
async def clear_export_cb(
    callback: CallbackQuery, user_id: int, session: AsyncSession
) -> None:
    await callback.answer("⏳ Excel tayyorlanmoqda...")
    try:
        txs = await TransactionRepository(session).get_for_export(user_id, None, None)
        from app.services.export_service import build_excel
        file_bytes = build_excel(txs)
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
    msg = callback.message
    if msg.text:
        await msg.edit_text(text, **kwargs)
    else:
        await msg.edit_caption(caption=text, **kwargs)


@router.callback_query(F.data == "clear_confirm")
async def clear_confirm_cb(
    callback: CallbackQuery, user_id: int, session: AsyncSession
) -> None:
    repo = TransactionRepository(session)
    deleted = await repo.delete_all_for_user(user_id)
    await _edit_message(
        callback,
        f"✅ <b>Tarix tozalandi</b>\n{SEP}\n{deleted} ta yozuv o'chirildi.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "clear_cancel")
async def clear_cancel_cb(callback: CallbackQuery) -> None:
    await _edit_message(callback, "↩️ Bekor qilindi.")
    await callback.answer()


# ── /export ───────────────────────────────────────────────────────────────────

@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    await message.answer(
        "📤 <b>Eksport</b>\n\nFayl formatini tanlang:",
        parse_mode="HTML", reply_markup=export_format_keyboard(),
    )


@router.callback_query(F.data.startswith("export:"))
async def export_format_chosen(callback: CallbackQuery) -> None:
    fmt = callback.data.split(":")[1]
    if fmt == "cancel":
        await callback.message.edit_text("❌ Bekor qilindi.")
        await callback.answer()
        return
    await callback.message.edit_text(
        "📅 <b>Qaysi davr uchun eksport?</b>",
        parse_mode="HTML", reply_markup=export_period_keyboard(fmt),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("export_period:"))
async def export_period_chosen(
    callback: CallbackQuery, user_id: int, session: AsyncSession
) -> None:
    _, fmt, period = callback.data.split(":")
    today = date.today()

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
        start = end = None
        label = "Barcha vaqt"

    await callback.message.edit_text("⏳ Fayl tayyorlanmoqda...")

    try:
        txs = await TransactionRepository(session).get_for_export(user_id, start, end)

        if fmt == "excel":
            from app.services.export_service import build_excel
            file_bytes = build_excel(txs)
            filename = f"harajat_{today}.xlsx"
        else:
            from app.services.export_service import build_csv
            file_bytes = build_csv(txs)
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
