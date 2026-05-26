"""
Matnli xabarlarni qayta ishlash — Gemini AI orqali tranzaksiyalarga aylantirish.

Yangi imkoniyatlar:
  - "//" orqali izoh qo'shish: "50k taxi // ish uchun"
  - Saqlanganidan keyin [✏️ Kategoriya | ↩️ Bekor] tugmalari
  - Kategoriya o'zgartirish
  - Duplicate tekshiruvi
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async
from django.db.models import Sum
from django.utils import timezone

from apps.transactions.models import Category, Transaction
from apps.users.models import TelegramUser
from bot.keyboards.inline import (
    CATEGORY_LIST,
    category_select_keyboard,
    confirm_transactions_keyboard,
    tx_quick_actions_keyboard,
)
from bot.keyboards.reply import MENU_BUTTONS, main_menu
from services import gemini

logger = logging.getLogger("bot")
router = Router(name="message")

SEP = "━" * 15

# Oxirgi saqlangan tranzaksiyalar: {user_telegram_id: [tx_id, ...]}
# /undo uchun ishlatiladi
_LAST_TX: dict[int, list[int]] = {}

CATEGORY_ICONS = {
    "ovqat": "🍽", "taxi": "🚕", "transport": "🚌",
    "kiyim": "👗", "internet": "🌐", "telefon": "📱",
    "uy": "🏠", "kommunal": "💡", "oqish": "📚",
    "salomatlik": "💊", "kongilochar": "🎭", "ish_haqi": "💼",
    "qarz": "🤝", "sovga": "🎁", "boshqa": "📌",
}

CATEGORY_NAMES = {
    "ovqat": "Ovqat", "taxi": "Taxi", "transport": "Transport",
    "kiyim": "Kiyim", "internet": "Internet", "telefon": "Telefon",
    "uy": "Uy", "kommunal": "Kommunal", "oqish": "O'qish",
    "salomatlik": "Salomatlik", "kongilochar": "Ko'ngilochar",
    "ish_haqi": "Ish haqi", "qarz": "Qarz", "sovga": "Sovg'a",
    "boshqa": "Boshqa",
}

PAYMENT_LABELS = {
    "cash": "Naqd pul", "card": "Karta",
    "click": "Click", "payme": "Payme",
    "bank": "Bank o'tkazma", "other": "Boshqa",
}

NUM_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]


def _fmt(amount, currency: str = "UZS") -> str:
    formatted = f"{float(amount):,.0f}".replace(",", " ")
    if currency == "USD":
        return f"$ {formatted}"
    if currency == "RUB":
        return f"{formatted} ₽"
    return f"{formatted} so'm"


def _signed(balance) -> str:
    bal = Decimal(str(balance))
    if bal >= 0:
        return f"+{_fmt(bal)}"
    return f"–{_fmt(abs(bal))}"


def _date_label(date_str: str) -> str:
    if not date_str or date_str == date.today().isoformat():
        return "Bugun"
    try:
        return date.fromisoformat(date_str).strftime("%d.%m.%Y")
    except ValueError:
        return date_str or "Bugun"


@sync_to_async
def _get_today_stats(user: TelegramUser):
    today = date.today()
    qs = Transaction.objects.filter(user=user, transaction_date=today)
    income = qs.filter(type="income").aggregate(t=Sum("amount"))["t"] or Decimal("0")
    expense = qs.filter(type="expense").aggregate(t=Sum("amount"))["t"] or Decimal("0")
    return income, expense, income - expense


@sync_to_async
def _get_all_stats(user: TelegramUser):
    qs = Transaction.objects.filter(user=user)
    income = qs.filter(type="income").aggregate(t=Sum("amount"))["t"] or Decimal("0")
    expense = qs.filter(type="expense").aggregate(t=Sum("amount"))["t"] or Decimal("0")
    return income, expense, income - expense


def _build_preview(items: list[dict]) -> str:
    lines = []
    for i, item in enumerate(items):
        num = NUM_EMOJIS[i] if i < len(NUM_EMOJIS) else f"{i + 1}."
        t_icon = "💰" if item["type"] == "income" else "💸"
        cat_name = CATEGORY_NAMES.get(item.get("category", "boshqa"), "Boshqa")
        amount_str = _fmt(item["amount"], item.get("currency", "UZS"))
        date_part = f"  •  {_date_label(item.get('date', ''))}"
        note = f"  · {item['note']}" if item.get("note") else ""
        lines.append(f"{num} {t_icon} {cat_name} — {amount_str}{date_part}{note}")
    return "\n".join(lines)


async def _get_or_create_category(user: TelegramUser, slug: str) -> Category:
    """Kategoriya olish yoki yaratish. "both" type ishlatiladi — type nomuvofiqligini oldini oladi."""
    name = CATEGORY_NAMES.get(slug, "Boshqa")
    icon = CATEGORY_ICONS.get(slug, "📌")
    # Avval standart (default) kategoriyani qidirish
    cat = await Category.objects.filter(slug=slug, is_default=True).afirst()
    if cat:
        return cat
    # Foydalanuvchi kategoriyasini yaratish
    cat, _ = await Category.objects.aget_or_create(
        slug=slug, user=user,
        defaults={"name": name, "icon": icon, "type": "both"},
    )
    return cat


async def _save_transactions(
    user: TelegramUser,
    items: list[dict],
    raw_text: str,
    extra_note: str | None = None,
) -> list[Transaction]:
    saved = []
    for item in items:
        try:
            cat = await _get_or_create_category(user, item.get("category", "boshqa"))
            t_date = date.fromisoformat(item["date"]) if item.get("date") else date.today()
            note = extra_note if extra_note else item.get("note", "")

            # Duplicate tekshiruvi: oxirgi 60 sekund ichida bir xil yozuv
            recent = timezone.now() - timedelta(seconds=60)
            existing = await Transaction.objects.filter(
                user=user,
                type=item["type"],
                amount=item["amount"],
                currency=item.get("currency", "UZS"),
                transaction_date=t_date,
                category=cat,
                created_at__gte=recent,
            ).afirst()
            if existing:
                saved.append(existing)
                continue

            tx = await Transaction.objects.acreate(
                user=user,
                type=item["type"],
                amount=item["amount"],
                currency=item.get("currency", "UZS"),
                category=cat,
                payment_method=item.get("payment_method", "cash"),
                note=note,
                transaction_date=t_date,
                raw_text=raw_text,
            )
            saved.append(tx)
        except Exception as e:
            logger.exception("Tranzaksiya saqlash xatosi: %s", e)
    return saved


async def _build_success_reply(user: TelegramUser, items: list[dict], saved: list[Transaction]) -> str:
    if not saved:
        return "❌ Saqlashda xato yuz berdi. Qayta urinib ko'ring."

    if len(saved) == 1:
        item = items[0]
        t_type = item["type"]
        amount_str = _fmt(item["amount"], item.get("currency", "UZS"))
        cat_name = CATEGORY_NAMES.get(item.get("category", "boshqa"), "Boshqa")
        payment = PAYMENT_LABELS.get(item.get("payment_method", "cash"), "Naqd pul")
        date_label = _date_label(item.get("date", ""))

        if t_type == "expense":
            header = "✅ Xarajat muvaffaqiyatli saqlandi"
            amount_line = f"💸 Summa: <b>{amount_str}</b>"
            cat_line = f"📌 Kategoriya: {cat_name}"
            inc, exp, bal = await _get_today_stats(user)
            stats_title = "📊 Bugungi statistika"
            stats_body = (
                f"• Jami chiqim:  {_fmt(exp)}\n"
                f"• Jami kirim:   {_fmt(inc)}\n"
                f"• Balans:       {_signed(bal)}"
            )
        else:
            header = "✅ Kirim muvaffaqiyatli saqlandi"
            amount_line = f"💰 Summa: <b>{amount_str}</b>"
            cat_line = f"📌 Manba: {cat_name}"
            inc, exp, bal = await _get_all_stats(user)
            stats_title = "📊 Umumiy balans"
            stats_body = (
                f"• Jami kirim:   {_fmt(inc)}\n"
                f"• Jami chiqim:  {_fmt(exp)}\n"
                f"• Sof balans:   {_signed(bal)}"
            )

        lines = [
            header, "",
            amount_line,
            cat_line,
            f"💳 To'lov turi: {payment}",
            f"📅 Sana: {date_label}",
        ]
        if item.get("note"):
            lines.append(f"📝 Izoh: {item['note']}")
        lines += ["", SEP, stats_title, "", stats_body]
        return "\n".join(lines)

    # Ko'p tranzaksiya
    num_expense = sum(1 for i in items if i["type"] == "expense")
    num_income = len(items) - num_expense

    if num_expense > 0 and num_income == 0:
        header = f"✅ {len(saved)} ta xarajat saqlandi"
        total = sum(i["amount"] for i in items)
        footer_lines = [SEP, "📊 Bugungi jami chiqim:", _fmt(total)]
    elif num_income > 0 and num_expense == 0:
        header = f"✅ {len(saved)} ta kirim saqlandi"
        total = sum(i["amount"] for i in items)
        footer_lines = [SEP, "📊 Bugungi jami kirim:", _fmt(total)]
    else:
        header = f"✅ {len(saved)} ta yozuv saqlandi"
        inc, exp, bal = await _get_today_stats(user)
        footer_lines = [
            SEP, "📊 Bugungi statistika", "",
            f"• Jami chiqim:  {_fmt(exp)}",
            f"• Jami kirim:   {_fmt(inc)}",
            f"• Balans:       {_signed(bal)}",
        ]

    lines = [header, ""]
    for idx, item in enumerate(items[:9]):
        num = NUM_EMOJIS[idx] if idx < len(NUM_EMOJIS) else f"{idx + 1}."
        cat_name = CATEGORY_NAMES.get(item.get("category", "boshqa"), "Boshqa")
        amount_str = _fmt(item["amount"], item.get("currency", "UZS"))
        lines.append(f"{num} {cat_name} — {amount_str}")

    if len(items) > 9:
        lines.append(f"... va yana {len(items) - 9} ta")

    lines += [""] + footer_lines
    return "\n".join(lines)


# ── Asosiy handler ───────────────────────────────────────────────────────────

@router.message(F.text & ~F.text.startswith("/") & ~F.text.in_(MENU_BUTTONS))
async def handle_text(message: Message, db_user: TelegramUser, state: FSMContext):
    raw = message.text.strip()

    # "//" orqali izoh ajratish: "50k taxi // ish uchun"
    extra_note: str | None = None
    if "//" in raw:
        text_part, _, note_part = raw.partition("//")
        text = text_part.strip()
        extra_note = note_part.strip() or None
    else:
        text = raw

    thinking_msg = await message.answer("⏳ Tahlil qilinmoqda...")

    try:
        items = await gemini.parse_text(text)
    except Exception:
        await thinking_msg.delete()
        await message.answer(
            "❌ AI xizmati bilan bog'lanishda xato\n\n"
            "Iltimos, bir ozdan keyin qayta urinib ko'ring.",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )
        return

    await thinking_msg.delete()

    if not items:
        await message.answer(
            "⚠️ Xabar tushunilmadi\n\n"
            "Iltimos aniqroq yozing:\n"
            "• summa\n"
            "• kirim yoki chiqim\n"
            "• kategoriya\n\n"
            "Misol:\n"
            "<i>\"Taxi uchun 25 ming ketdi\"</i>\n\n"
            "Izoh qo'shish uchun <code>//</code> ishlating:\n"
            "<i>\"50k taxi // ish uchun\"</i>",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )
        return

    if len(items) == 1:
        saved = await _save_transactions(db_user, items, raw, extra_note)
        if saved:
            _LAST_TX[db_user.telegram_id] = [tx.id for tx in saved]
        reply = await _build_success_reply(db_user, items, saved)
        kb = tx_quick_actions_keyboard(saved[0].id) if saved else main_menu()
        await message.answer(reply, parse_mode="HTML", reply_markup=kb)
        return

    preview = _build_preview(items)
    await state.update_data(pending_items=items, raw_text=raw, extra_note=extra_note)

    await message.answer(
        f"📋 <b>{len(items)} ta tranzaksiya topildi:</b>\n\n"
        f"{preview}\n\n"
        f"{SEP}\n"
        "Hammasini saqlashni tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=confirm_transactions_keyboard(len(items)),
    )


@router.callback_query(F.data == "confirm_save")
async def confirm_save(callback: CallbackQuery, db_user: TelegramUser, state: FSMContext):
    data = await state.get_data()
    items = data.get("pending_items", [])
    raw_text = data.get("raw_text", "")
    extra_note = data.get("extra_note")

    await state.clear()

    if not items:
        await callback.answer("Saqlash uchun ma'lumot topilmadi.", show_alert=True)
        return

    saved = await _save_transactions(db_user, items, raw_text, extra_note)
    if saved:
        _LAST_TX[db_user.telegram_id] = [tx.id for tx in saved]

    reply = await _build_success_reply(db_user, items, saved)
    await callback.message.edit_text(reply, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "cancel_save")
async def cancel_save(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi")
    await callback.answer()


# ── Inline undo (tezkor bekor qilish) ───────────────────────────────────────

@router.callback_query(F.data.startswith("tx:undo:"))
async def tx_undo_inline(callback: CallbackQuery, db_user: TelegramUser) -> None:
    try:
        tx_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Xato.", show_alert=True)
        return
    deleted, _ = await Transaction.objects.filter(id=tx_id, user=db_user).adelete()
    if deleted:
        _LAST_TX.pop(db_user.telegram_id, None)
        try:
            await callback.message.edit_text("↩️ Yozuv bekor qilindi.")
        except Exception:
            pass
    else:
        await callback.answer("❌ Yozuv topilmadi yoki allaqachon o'chirilgan.", show_alert=True)
        return
    await callback.answer()


# ── Kategoriya o'zgartirish ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("tx:cat_change:"))
async def tx_cat_change(callback: CallbackQuery, db_user: TelegramUser) -> None:
    parts = callback.data.split(":")
    tx_id = int(parts[2])
    back_page = int(parts[3]) if len(parts) > 3 else 0

    tx = await Transaction.objects.filter(id=tx_id, user=db_user).afirst()
    if not tx:
        await callback.answer("❌ Yozuv topilmadi.", show_alert=True)
        return
    await callback.message.edit_text(
        "📌 <b>Kategoriyani tanlang:</b>",
        parse_mode="HTML",
        reply_markup=category_select_keyboard(tx_id, back_page),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tx:cat_set:"))
async def tx_cat_set(callback: CallbackQuery, db_user: TelegramUser) -> None:
    parts = callback.data.split(":")
    tx_id = int(parts[2])
    slug = parts[3]
    back_page = int(parts[4]) if len(parts) > 4 else 0

    tx = await Transaction.objects.filter(id=tx_id, user=db_user).select_related("category").afirst()
    if not tx:
        await callback.answer("❌ Yozuv topilmadi.", show_alert=True)
        return

    cat = await _get_or_create_category(db_user, slug)
    # aupdate ishlatiladi — auto_now field uchun xavfsiz
    await Transaction.objects.filter(id=tx_id, user=db_user).aupdate(category=cat)

    from bot.keyboards.inline import tx_detail_keyboard as _tx_detail_kb
    icon = CATEGORY_ICONS.get(slug, "📌")
    name = CATEGORY_NAMES.get(slug, "Boshqa")
    await callback.message.edit_text(
        f"✅ Kategoriya o'zgartirildi:\n\n"
        f"{icon} <b>{name}</b>\n\n"
        f"<code>#{tx.id}</code> — {_fmt(tx.amount, tx.currency)}",
        parse_mode="HTML",
        reply_markup=_tx_detail_kb(tx_id, back_page),
    )
    await callback.answer("✅ Saqlandi!")
