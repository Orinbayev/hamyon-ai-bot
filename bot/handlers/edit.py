"""
Tranzaksiyani tahrirlash — FSM orqali miqdor, sana, izoh o'zgartirish.
"""

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from apps.transactions.models import Transaction
from apps.users.models import TelegramUser
from bot.keyboards.inline import tx_detail_keyboard

logger = logging.getLogger("bot")
router = Router(name="edit")

MONTHS_UZ = {
    1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
    5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
    9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr",
}

CAT_ICONS = {
    "ovqat": "🍽", "taxi": "🚕", "transport": "🚌",
    "kiyim": "👗", "internet": "🌐", "telefon": "📱",
    "uy": "🏠", "kommunal": "💡", "oqish": "📚",
    "salomatlik": "💊", "kongilochar": "🎭", "ish_haqi": "💼",
    "qarz": "🤝", "sovga": "🎁", "boshqa": "📌",
}

PAYMENT_LABELS = {
    "cash": "Naqd pul", "card": "Karta",
    "click": "Click", "payme": "Payme",
    "bank": "Bank o'tkazma", "other": "Boshqa",
}


class TxEditState(StatesGroup):
    waiting_amount = State()
    waiting_date   = State()
    waiting_note   = State()


def _fmt_amount(amount, currency="UZS") -> str:
    n = f"{float(amount):,.0f}".replace(",", " ")
    if currency == "USD":
        return f"$ {n}"
    if currency == "RUB":
        return f"{n} ₽"
    return f"{n} so'm"


def _tx_detail_text(tx: Transaction) -> str:
    icon = "💰 Kirim" if tx.type == "income" else "💸 Xarajat"
    cat_name = tx.category.name if tx.category else "Boshqa"
    cat_icon = CAT_ICONS.get(tx.category.slug if tx.category else "boshqa", "📌")
    payment = PAYMENT_LABELS.get(tx.payment_method, "Naqd pul")
    d = tx.transaction_date
    date_str = f"{d.day} {MONTHS_UZ[d.month]} {d.year}"
    lines = [
        f"📋 <b>#{tx.id}</b> — {icon}",
        "━━━━━━━━━━━━━━━",
        f"📌 Kategoriya:   {cat_icon} {cat_name}",
        f"💰 Summa:        <b>{_fmt_amount(tx.amount, tx.currency)}</b>",
        f"💳 To'lov turi:  {payment}",
        f"📅 Sana:         {date_str}",
    ]
    if tx.note:
        lines.append(f"📝 Izoh:          {tx.note}")
    return "\n".join(lines)


def _parse_amount(text: str) -> Decimal | None:
    t = text.strip().lower().replace(" ", "").replace(",", ".")
    multiplier = Decimal("1")
    if t.endswith("k"):
        multiplier = Decimal("1000")
        t = t[:-1]
    elif t.endswith("ming"):
        multiplier = Decimal("1000")
        t = t[:-4]
    elif t.endswith("mln") or t.endswith("million"):
        multiplier = Decimal("1000000")
        t = t.replace("million", "").replace("mln", "")
    # Remove currency symbols
    for sym in ["so'm", "sum", "uzs", "usd", "$", "rub", "₽"]:
        t = t.replace(sym, "")
    t = t.strip()
    try:
        return Decimal(t) * multiplier
    except InvalidOperation:
        return None


def _parse_date(text: str) -> date | None:
    text = text.strip()
    for fmt in ["%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%y", "%d-%m-%Y"]:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


# ── Tranzaksiya detail ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("tx:view:"))
async def tx_view(callback: CallbackQuery, db_user: TelegramUser) -> None:
    """Tranzaksiya detallarini ko'rsatish."""
    parts = callback.data.split(":")
    tx_id = int(parts[2])
    back_page = int(parts[3]) if len(parts) > 3 else 0

    tx = await Transaction.objects.filter(id=tx_id, user=db_user).select_related("category").afirst()
    if not tx:
        await callback.answer("❌ Yozuv topilmadi.", show_alert=True)
        return

    text = _tx_detail_text(tx)
    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=tx_detail_keyboard(tx_id, back_page),
        )
    except Exception:
        pass
    await callback.answer()


# ── Miqdor tahrirlash ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("tx:edit_amount:"))
async def tx_edit_amount_start(callback: CallbackQuery, db_user: TelegramUser, state: FSMContext) -> None:
    parts = callback.data.split(":")
    tx_id = int(parts[2])
    back_page = int(parts[3]) if len(parts) > 3 else 0

    tx = await Transaction.objects.filter(id=tx_id, user=db_user).afirst()
    if not tx:
        await callback.answer("❌ Topilmadi.", show_alert=True)
        return

    await state.update_data(editing_tx_id=tx_id, back_page=back_page)
    await state.set_state(TxEditState.waiting_amount)

    await callback.message.edit_text(
        f"💰 <b>Yangi miqdorni yuboring</b>\n\n"
        f"Hozirgi: <b>{_fmt_amount(tx.amount, tx.currency)}</b>\n\n"
        f"Misol: <code>45000</code>  yoki  <code>45k</code>  yoki  <code>1.5mln</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(TxEditState.waiting_amount)
async def tx_edit_amount_save(message: Message, db_user: TelegramUser, state: FSMContext) -> None:
    data = await state.get_data()
    tx_id = data.get("editing_tx_id")
    back_page = data.get("back_page", 0)
    await state.clear()

    amount = _parse_amount(message.text or "")
    if not amount or amount <= 0:
        await message.answer(
            "❌ Noto'g'ri miqdor.\n\n"
            "Raqam yuboring: <code>45000</code> yoki <code>45k</code>",
            parse_mode="HTML",
        )
        return

    tx = await Transaction.objects.filter(id=tx_id, user=db_user).select_related("category").afirst()
    if not tx:
        await message.answer("❌ Yozuv topilmadi.")
        return

    old_amount = tx.amount
    await Transaction.objects.filter(id=tx_id, user=db_user).aupdate(amount=amount)
    tx.amount = amount

    await message.answer(
        f"✅ <b>Miqdor o'zgartirildi</b>\n\n"
        f"Avval: {_fmt_amount(old_amount, tx.currency)}\n"
        f"Yangi: <b>{_fmt_amount(amount, tx.currency)}</b>",
        parse_mode="HTML",
        reply_markup=tx_detail_keyboard(tx_id, back_page),
    )


# ── Sana tahrirlash ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("tx:edit_date:"))
async def tx_edit_date_start(callback: CallbackQuery, db_user: TelegramUser, state: FSMContext) -> None:
    parts = callback.data.split(":")
    tx_id = int(parts[2])
    back_page = int(parts[3]) if len(parts) > 3 else 0

    tx = await Transaction.objects.filter(id=tx_id, user=db_user).afirst()
    if not tx:
        await callback.answer("❌ Topilmadi.", show_alert=True)
        return

    await state.update_data(editing_tx_id=tx_id, back_page=back_page)
    await state.set_state(TxEditState.waiting_date)

    d = tx.transaction_date
    await callback.message.edit_text(
        f"📅 <b>Yangi sanani yuboring</b>\n\n"
        f"Hozirgi: <b>{d.day}.{d.month:02d}.{d.year}</b>\n\n"
        f"Format: <code>DD.MM.YYYY</code>\n"
        f"Misol: <code>{date.today().strftime('%d.%m.%Y')}</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(TxEditState.waiting_date)
async def tx_edit_date_save(message: Message, db_user: TelegramUser, state: FSMContext) -> None:
    data = await state.get_data()
    tx_id = data.get("editing_tx_id")
    back_page = data.get("back_page", 0)
    await state.clear()

    new_date = _parse_date(message.text or "")
    if not new_date:
        await message.answer(
            "❌ Noto'g'ri format.\n\n"
            "Misol: <code>26.05.2026</code>",
            parse_mode="HTML",
        )
        return

    if new_date > date.today():
        await message.answer("❌ Kelajak sanani kiritib bo'lmaydi.")
        return

    tx = await Transaction.objects.filter(id=tx_id, user=db_user).select_related("category").afirst()
    if not tx:
        await message.answer("❌ Yozuv topilmadi.")
        return

    old_date = tx.transaction_date
    await Transaction.objects.filter(id=tx_id, user=db_user).aupdate(transaction_date=new_date)
    tx.transaction_date = new_date

    await message.answer(
        f"✅ <b>Sana o'zgartirildi</b>\n\n"
        f"Avval: {old_date.strftime('%d.%m.%Y')}\n"
        f"Yangi: <b>{new_date.strftime('%d.%m.%Y')}</b>",
        parse_mode="HTML",
        reply_markup=tx_detail_keyboard(tx_id, back_page),
    )


# ── Izoh tahrirlash ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("tx:edit_note:"))
async def tx_edit_note_start(callback: CallbackQuery, db_user: TelegramUser, state: FSMContext) -> None:
    parts = callback.data.split(":")
    tx_id = int(parts[2])
    back_page = int(parts[3]) if len(parts) > 3 else 0

    tx = await Transaction.objects.filter(id=tx_id, user=db_user).afirst()
    if not tx:
        await callback.answer("❌ Topilmadi.", show_alert=True)
        return

    await state.update_data(editing_tx_id=tx_id, back_page=back_page)
    await state.set_state(TxEditState.waiting_note)

    current = f"<i>{tx.note}</i>" if tx.note else "<i>(bo'sh)</i>"
    await callback.message.edit_text(
        f"📝 <b>Izoh yozing</b>\n\n"
        f"Hozirgi: {current}\n\n"
        f"Yangi izohni yuboring.\n"
        f"O'chirish uchun: <code>-</code>",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(TxEditState.waiting_note)
async def tx_edit_note_save(message: Message, db_user: TelegramUser, state: FSMContext) -> None:
    data = await state.get_data()
    tx_id = data.get("editing_tx_id")
    back_page = data.get("back_page", 0)
    await state.clear()

    new_note = "" if (message.text or "").strip() == "-" else (message.text or "").strip()

    tx = await Transaction.objects.filter(id=tx_id, user=db_user).select_related("category").afirst()
    if not tx:
        await message.answer("❌ Yozuv topilmadi.")
        return

    await Transaction.objects.filter(id=tx_id, user=db_user).aupdate(note=new_note)
    tx.note = new_note

    label = f"<i>{new_note}</i>" if new_note else "<i>(o'chirildi)</i>"
    await message.answer(
        f"✅ <b>Izoh o'zgartirildi</b>\n\n"
        f"Yangi: {label}",
        parse_mode="HTML",
        reply_markup=tx_detail_keyboard(tx_id, back_page),
    )
