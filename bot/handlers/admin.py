"""
Admin panel handler — faqat settings.ADMIN_IDS uchun.

Buyruqlar:
  /admin   — panel ochish
  /whoami  — o'z Telegram ID ni bilish

Callback patterns:
  adm:menu           — bosh menyu
  adm:stats          — umumiy statistika
  adm:today          — bugungi ko'rsat
  adm:users:{page}   — foydalanuvchilar ro'yxati
  adm:user:{id}      — user detail
  adm:export:{id}    — user Excel
  adm:clear:{id}     — tozalash tasdiqlash
  adm:clear_ok:{id}  — tozalashni tasdiqlash
  adm:broadcast      — xabar yuborish
  adm:broadcast_ok   — yuborishni tasdiqlash
  adm:about          — bot haqida
  adm:gemini         — Gemini token holati
  adm:channels       — majburiy kanallar ro'yxati
  adm:ch_add         — kanal qo'shish (tur tanlash)
  adm:ch_type:pub    — public kanal qo'shish (@username)
  adm:ch_type:priv   — shaxsiy kanal qo'shish (ID + invite)
  adm:ch_del:{id}    — kanal o'chirish tasdiqlash
  adm:ch_del_ok:{id} — kanal o'chirishni tasdiqlash
  adm:ch_tog:{id}    — kanal faol/nofaol almashtirish
"""

import asyncio
import logging
from datetime import date, timedelta

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.transactions.models import Transaction
from apps.users.models import RequiredChannel, TelegramUser
from services import export as export_service
from services.token_tracker import tracker as gemini_tracker

logger = logging.getLogger("bot.admin")
router = Router(name="admin")

SEP = "━" * 16
USERS_PER_PAGE = 10


class AdminState(StatesGroup):
    waiting_broadcast_text = State()
    confirm_broadcast = State()


class ChannelAddState(StatesGroup):
    waiting_username = State()    # public: @username
    waiting_channel_id = State()  # private: -100xxxxxxxxxx
    waiting_invite_link = State() # private: https://t.me/+xxxxxx


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_admin(tg_id: int) -> bool:
    return tg_id in getattr(settings, "ADMIN_IDS", [])


def _fname(full_name: str) -> str:
    parts = (full_name or "").split()
    return parts[0] if parts else "Admin"


def _fmt(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ") + " so'm"


def _fmts(v: float) -> str:
    sign = "+" if v >= 0 else "–"
    return f"{sign}{abs(v):,.0f}".replace(",", " ") + " so'm"


def _pct_bar(pct: float, width: int = 10) -> str:
    filled = min(round(pct / 100 * width), width)
    return "▓" * filled + "░" * (width - filled)


async def _safe_edit(callback: CallbackQuery, text: str, **kwargs) -> None:
    try:
        if callback.message.text:
            await callback.message.edit_text(text, **kwargs)
        else:
            await callback.message.edit_caption(caption=text, **kwargs)
    except TelegramBadRequest:
        await callback.message.answer(text, **kwargs)


# ── Keyboards ──────────────────────────────────────────────────────────────────

def _main_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats"),
        InlineKeyboardButton(text="📅 Bugun", callback_data="adm:today"),
    )
    b.row(
        InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="adm:users:0"),
        InlineKeyboardButton(text="ℹ️ Bot haqida", callback_data="adm:about"),
    )
    b.row(
        InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="adm:broadcast"),
        InlineKeyboardButton(text="🤖 Gemini", callback_data="adm:gemini"),
    )
    b.row(
        InlineKeyboardButton(text="📡 Majburiy kanallar", callback_data="adm:channels"),
    )
    return b.as_markup()


def _back_kb(target: str = "adm:menu") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=target))
    return b.as_markup()


# ── /whoami ────────────────────────────────────────────────────────────────────

@router.message(Command("whoami"))
async def cmd_whoami(message: Message) -> None:
    await message.answer(
        f"🆔 Sizning Telegram ID: <code>{message.from_user.id}</code>\n\n"
        "Admin qo'shish uchun bu ID ni <code>ADMIN_IDS</code> env ga yozing.",
        parse_mode="HTML",
    )


# ── /admin ─────────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, db_user: TelegramUser, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    name = _fname(db_user.full_name)
    await message.answer(
        f"🛠 <b>Admin panel</b>\n{SEP}\n"
        f"Xush kelibsiz, <b>{name}</b>!\n\n"
        "Bo'limni tanlang:",
        parse_mode="HTML",
        reply_markup=_main_kb(),
    )


@router.callback_query(F.data == "adm:menu")
async def adm_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await state.clear()
    await _safe_edit(
        callback,
        f"🛠 <b>Admin panel</b>\n{SEP}\nBo'limni tanlang:",
        parse_mode="HTML",
        reply_markup=_main_kb(),
    )
    await callback.answer()


# ── 📊 Umumiy statistika ───────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:stats")
async def adm_stats(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("⏳ Hisoblanmoqda...")
    text = await _fetch_stats()
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_back_kb())
    await callback.answer()


@sync_to_async
def _fetch_stats() -> str:
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today.replace(day=1)

    total_users = TelegramUser.objects.count()
    new_today = TelegramUser.objects.filter(created_at__date=today).count()
    active_today = (
        Transaction.objects.filter(transaction_date=today)
        .values("user_id").distinct().count()
    )
    active_week = (
        Transaction.objects.filter(transaction_date__gte=week_ago)
        .values("user_id").distinct().count()
    )

    total_tx = Transaction.objects.count()
    tx_today = Transaction.objects.filter(transaction_date=today).count()
    tx_week = Transaction.objects.filter(transaction_date__gte=week_ago).count()
    tx_month = Transaction.objects.filter(transaction_date__gte=month_ago).count()

    agg = Transaction.objects.aggregate(
        income=Coalesce(
            Sum("amount", filter=Q(type="income")), Value(0), output_field=DecimalField()
        ),
        expense=Coalesce(
            Sum("amount", filter=Q(type="expense")), Value(0), output_field=DecimalField()
        ),
    )
    agg_today = Transaction.objects.filter(transaction_date=today).aggregate(
        income=Coalesce(
            Sum("amount", filter=Q(type="income")), Value(0), output_field=DecimalField()
        ),
        expense=Coalesce(
            Sum("amount", filter=Q(type="expense")), Value(0), output_field=DecimalField()
        ),
    )

    income = float(agg["income"])
    expense = float(agg["expense"])
    income_t = float(agg_today["income"])
    expense_t = float(agg_today["expense"])

    return (
        f"📊 <b>Umumiy statistika</b>\n{SEP}\n\n"
        f"👥 <b>Foydalanuvchilar:</b>\n"
        f"   Jami:         <b>{total_users}</b>\n"
        f"   Bugun yangi:  <b>{new_today}</b>\n"
        f"   Faol (bugun): <b>{active_today}</b>\n"
        f"   Faol (hafta): <b>{active_week}</b>\n\n"
        f"{SEP}\n\n"
        f"📋 <b>Tranzaksiyalar:</b>\n"
        f"   Jami:   <b>{total_tx}</b>\n"
        f"   Bugun:  <b>{tx_today}</b>\n"
        f"   Hafta:  <b>{tx_week}</b>\n"
        f"   Oy:     <b>{tx_month}</b>\n\n"
        f"{SEP}\n\n"
        f"💰 <b>Moliyaviy (jami):</b>\n"
        f"   Kirim:   <b>{_fmt(income)}</b>\n"
        f"   Chiqim:  <b>{_fmt(expense)}</b>\n"
        f"   Balans:  <b>{_fmts(income - expense)}</b>\n\n"
        f"💰 <b>Bugun:</b>\n"
        f"   Kirim:   <b>{_fmt(income_t)}</b>\n"
        f"   Chiqim:  <b>{_fmt(expense_t)}</b>"
    )


# ── 📅 Bugungi faollik ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:today")
async def adm_today(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("⏳...")
    text = await _fetch_today()
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_back_kb())
    await callback.answer()


@sync_to_async
def _fetch_today() -> str:
    today = date.today()
    txs = list(
        Transaction.objects.filter(transaction_date=today)
        .select_related("user", "category")
        .order_by("-created_at")[:20]
    )
    total = Transaction.objects.filter(transaction_date=today).count()
    agg = Transaction.objects.filter(transaction_date=today).aggregate(
        income=Coalesce(
            Sum("amount", filter=Q(type="income")), Value(0), output_field=DecimalField()
        ),
        expense=Coalesce(
            Sum("amount", filter=Q(type="expense")), Value(0), output_field=DecimalField()
        ),
    )

    lines = [
        f"📅 <b>Bugun — {today.strftime('%d.%m.%Y')}</b>\n{SEP}\n",
        f"📋 Jami tranzaksiya: <b>{total}</b>",
        f"💰 Kirim:  <b>{_fmt(float(agg['income']))}</b>",
        f"💸 Chiqim: <b>{_fmt(float(agg['expense']))}</b>",
        "",
    ]
    if txs:
        lines.append(f"<b>Oxirgi {min(len(txs), 20)} ta:</b>")
        for t in txs:
            icon = "💰" if t.type == "income" else "💸"
            cat = t.category.name if t.category else "Boshqa"
            amt = f"{float(t.amount):,.0f}".replace(",", " ")
            name = (t.user.full_name or "?")[:16]
            lines.append(f"{icon} {name} — {cat} {amt} {t.currency}")
    else:
        lines.append("🔕 Bugun hech qanday tranzaksiya yo'q.")

    return "\n".join(lines)


# ── 👥 Foydalanuvchilar ro'yxati ───────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm:users:"))
async def adm_users(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    page = int(callback.data.split(":")[2])
    text, kb = await _fetch_users_page(page)
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@sync_to_async
def _fetch_users_page(page: int) -> tuple[str, InlineKeyboardMarkup]:
    total = TelegramUser.objects.count()
    offset = page * USERS_PER_PAGE
    total_pages = max(1, (total + USERS_PER_PAGE - 1) // USERS_PER_PAGE)

    users = list(
        TelegramUser.objects
        .annotate(
            _tx=Count("transactions"),
            _exp=Coalesce(
                Sum("transactions__amount", filter=Q(transactions__type="expense")),
                Value(0), output_field=DecimalField(),
            ),
        )
        .order_by("-_tx")[offset : offset + USERS_PER_PAGE]
    )

    current_page = page + 1
    lines = [
        f"👥 <b>Foydalanuvchilar</b>  "
        f"<b>{current_page}/{total_pages}</b>  ({total} ta)\n{SEP}\n"
    ]
    start_n = offset + 1
    for i, u in enumerate(users, start_n):
        uname = f"@{u.username}" if u.username else "—"
        exp_str = f"{float(u._exp):,.0f}".replace(",", " ")
        status = "🟢" if u.is_active else "🔴"
        lines.append(
            f"{status} <b>{i}.</b> {u.full_name[:20]}  {uname}\n"
            f"    📋 {u._tx}  •  💸 {exp_str} so'm\n"
        )

    b = InlineKeyboardBuilder()
    for u in users:
        label = f"{'🟢' if u.is_active else '🔴'} {u.full_name[:28]}"
        b.row(InlineKeyboardButton(text=label, callback_data=f"adm:user:{u.id}"))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"adm:users:{page - 1}"))
    nav.append(InlineKeyboardButton(
        text=f"📄 {current_page}/{total_pages}",
        callback_data="adm:menu",
    ))
    if offset + USERS_PER_PAGE < total:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"adm:users:{page + 1}"))
    b.row(*nav)
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))

    return "\n".join(lines), b.as_markup()


# ── 👤 User detail ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^adm:user:\d+$"))
async def adm_user_detail(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    text, kb = await _fetch_user_detail(user_id)
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@sync_to_async
def _fetch_user_detail(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    try:
        u = TelegramUser.objects.get(id=user_id)
    except TelegramUser.DoesNotExist:
        b = InlineKeyboardBuilder()
        b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:users:0"))
        return "❌ Foydalanuvchi topilmadi.", b.as_markup()

    agg = Transaction.objects.filter(user=u).aggregate(
        total=Count("id"),
        income=Coalesce(
            Sum("amount", filter=Q(type="income")), Value(0), output_field=DecimalField()
        ),
        expense=Coalesce(
            Sum("amount", filter=Q(type="expense")), Value(0), output_field=DecimalField()
        ),
    )
    income = float(agg["income"])
    expense = float(agg["expense"])

    last_txs = list(
        Transaction.objects.filter(user=u)
        .select_related("category")
        .order_by("-transaction_date", "-created_at")[:8]
    )

    uname = f"@{u.username}" if u.username else "—"
    status_txt = "Faol ✅" if u.is_active else "Bloklangan 🔴"

    lines = [
        f"👤 <b>{u.full_name}</b>  {uname}\n{SEP}\n",
        f"🆔 Telegram ID:     <code>{u.telegram_id}</code>",
        f"📅 Ro'yxatdan:      {u.created_at.strftime('%d.%m.%Y %H:%M')}",
        f"🔄 Yangilangan:     {u.updated_at.strftime('%d.%m.%Y %H:%M')}",
        f"🟢 Holat:           {status_txt}\n",
        f"📋 Tranzaksiyalar:  <b>{agg['total']}</b>",
        f"💰 Kirim:           <b>{_fmt(income)}</b>",
        f"💸 Chiqim:          <b>{_fmt(expense)}</b>",
        f"📈 Balans:          <b>{_fmts(income - expense)}</b>",
    ]

    if last_txs:
        lines.append(f"\n{SEP}\n🕐 <b>Oxirgi {len(last_txs)} ta tranzaksiya:</b>\n")
        nums = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
        for i, t in enumerate(last_txs):
            icon = "💰" if t.type == "income" else "💸"
            cat = t.category.name if t.category else "Boshqa"
            amt = f"{float(t.amount):,.0f}".replace(",", " ")
            lines.append(
                f"{nums[i]} {icon} {cat} — {amt} {t.currency}"
                f"  <i>({t.transaction_date.strftime('%d.%m')})</i>"
            )

    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📊 Excel", callback_data=f"adm:export:{u.id}"),
        InlineKeyboardButton(text="🗑 Tarixni tozalash", callback_data=f"adm:clear:{u.id}"),
    )
    if u.is_active:
        b.row(InlineKeyboardButton(
            text="🚫 Bloklash",
            callback_data=f"adm:block:{u.id}",
        ))
    else:
        b.row(InlineKeyboardButton(
            text="✅ Faollashtirish",
            callback_data=f"adm:unblock:{u.id}",
        ))
    b.row(InlineKeyboardButton(text="🔙 Foydalanuvchilar", callback_data="adm:users:0"))

    return "\n".join(lines), b.as_markup()


# ── Admin: block / unblock user ────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^adm:(block|unblock):\d+$"))
async def adm_toggle_user(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    action, user_id = parts[1], int(parts[2])
    u = await TelegramUser.objects.aget(id=user_id)
    u.is_active = action == "unblock"
    await u.asave(update_fields=["is_active"])
    status = "faollashtirildi ✅" if u.is_active else "bloklandi 🚫"
    await callback.answer(f"Foydalanuvchi {status}", show_alert=True)
    text, kb = await _fetch_user_detail(user_id)
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=kb)


# ── Admin: export user Excel ───────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^adm:export:\d+$"))
async def adm_export_user(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    await callback.answer("⏳ Excel tayyorlanmoqda...")
    try:
        u = await TelegramUser.objects.aget(id=user_id)
        file_bytes = await export_service.export_excel(u)
        doc = BufferedInputFile(
            file_bytes.read(),
            filename=f"user_{u.telegram_id}_{date.today()}.xlsx",
        )
        await callback.message.answer_document(
            doc,
            caption=f"📊 <b>{u.full_name}</b> — barcha tranzaksiyalar",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.exception("Admin export xatosi: %s", e)
        await callback.message.answer("❌ Eksport qilishda xato yuz berdi.")


# ── Admin: clear user history ──────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^adm:clear:\d+$"))
async def adm_clear_ask(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    count = await Transaction.objects.filter(user_id=user_id).acount()
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🗑 Ha, tozalash", callback_data=f"adm:clear_ok:{user_id}"),
        InlineKeyboardButton(text="❌ Bekor", callback_data=f"adm:user:{user_id}"),
    )
    await _safe_edit(
        callback,
        f"⚠️ <b>Tarixni tozalash</b>\n{SEP}\n"
        f"Bu foydalanuvchining <b>{count}</b> ta yozuvi o'chiriladi.\n\n"
        "Tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=b.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^adm:clear_ok:\d+$"))
async def adm_clear_confirm(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    deleted, _ = await Transaction.objects.filter(user_id=user_id).adelete()
    await _safe_edit(
        callback,
        f"✅ <b>Tarix tozalandi</b>\n{SEP}\n{deleted} ta yozuv o'chirildi.",
        parse_mode="HTML",
        reply_markup=_back_kb("adm:users:0"),
    )
    await callback.answer()


# ── 📢 Broadcast ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:broadcast")
async def adm_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.waiting_broadcast_text)
    await _safe_edit(
        callback,
        f"📢 <b>Xabar yuborish</b>\n{SEP}\n"
        "Barcha faol foydalanuvchilarga yuboriladigan xabarni yozing:\n\n"
        "<i>HTML teglari qo'llab-quvvatlanadi: &lt;b&gt;, &lt;i&gt;, &lt;code&gt;</i>",
        parse_mode="HTML",
        reply_markup=_back_kb("adm:menu"),
    )
    await callback.answer()


@router.message(AdminState.waiting_broadcast_text)
async def adm_broadcast_text(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("⚠️ Matn yozing.")
        return

    await state.update_data(broadcast_text=text)
    await state.set_state(AdminState.confirm_broadcast)

    count = await TelegramUser.objects.filter(is_active=True).acount()

    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(
            text=f"✅ {count} ta foydalanuvchiga yuborish",
            callback_data="adm:broadcast_ok",
        ),
    )
    b.row(
        InlineKeyboardButton(text="✏️ Qayta yozish", callback_data="adm:broadcast"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="adm:menu"),
    )

    await message.answer(
        f"📢 <b>Ko'rinish:</b>\n{SEP}\n\n"
        f"{text}\n\n{SEP}\n"
        f"<b>{count}</b> ta faol foydalanuvchiga yuboriladi.",
        parse_mode="HTML",
        reply_markup=b.as_markup(),
    )


@router.callback_query(F.data == "adm:broadcast_ok")
async def adm_broadcast_send(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    text = data.get("broadcast_text", "")
    await state.clear()

    if not text:
        await callback.answer("❌ Xabar topilmadi.", show_alert=True)
        return

    user_ids = await _get_active_tg_ids()
    await callback.message.edit_text(f"⏳ Yuborilmoqda...  0 / {len(user_ids)}")

    bot: Bot = callback.bot
    sent = failed = 0
    for tg_id in user_ids:
        try:
            await bot.send_message(tg_id, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        if (sent + failed) % 20 == 0:
            await asyncio.sleep(0.5)

    await callback.message.edit_text(
        f"✅ <b>Xabar yuborildi</b>\n{SEP}\n"
        f"✅ Muvaffaqiyatli: <b>{sent}</b>\n"
        f"❌ Xato / blok:    <b>{failed}</b>",
        parse_mode="HTML",
        reply_markup=_back_kb("adm:menu"),
    )
    await callback.answer()


@sync_to_async
def _get_active_tg_ids() -> list[int]:
    return list(
        TelegramUser.objects.filter(is_active=True).values_list("telegram_id", flat=True)
    )


# ── ℹ️ Bot haqida ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:about")
async def adm_about(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    text = await _fetch_about()
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=_back_kb("adm:menu"))
    await callback.answer()


@sync_to_async
def _fetch_about() -> str:
    today = date.today()
    new_today = TelegramUser.objects.filter(created_at__date=today).count()
    new_week = TelegramUser.objects.filter(
        created_at__date__gte=today - timedelta(days=7)
    ).count()
    new_month = TelegramUser.objects.filter(
        created_at__date__gte=today.replace(day=1)
    ).count()
    total = TelegramUser.objects.count()
    blocked = TelegramUser.objects.filter(is_active=False).count()

    top = list(
        TelegramUser.objects
        .annotate(_tx=Count("transactions"))
        .order_by("-_tx")[:5]
    )
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    top_lines = [
        f"  {medals[i]} {u.full_name[:20]} — {u._tx} ta"
        for i, u in enumerate(top) if u._tx > 0
    ]

    return (
        f"ℹ️ <b>Bot haqida</b>\n{SEP}\n\n"
        f"👥 <b>Foydalanuvchilar:</b>\n"
        f"  Jami:         <b>{total}</b>\n"
        f"  Bloklangan:   <b>{blocked}</b>\n"
        f"  Faol:         <b>{total - blocked}</b>\n\n"
        f"📈 <b>Yangilar:</b>\n"
        f"  Bugun:  <b>{new_today}</b>\n"
        f"  Hafta:  <b>{new_week}</b>\n"
        f"  Oy:     <b>{new_month}</b>\n\n"
        f"{SEP}\n\n"
        f"🏆 <b>TOP-5 faol foydalanuvchi:</b>\n"
        + ("\n".join(top_lines) if top_lines else "  Hali tranzaksiya yo'q")
    )


# ── 🤖 Gemini token holati ─────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:gemini")
async def adm_gemini(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return

    s = gemini_tracker.stats()
    sess_req = gemini_tracker.session_requests
    sess_tok = gemini_tracker.session_tokens

    warn_req = " ⚠️" if s.req_pct >= 80 else ""
    warn_tok = " ⚠️" if s.tok_pct >= 80 else ""

    text = (
        f"🤖 <b>Gemini token holati</b>\n{SEP}\n\n"
        f"📅 Sana:   <b>{s.day}</b>\n"
        f"🔧 Model:  <code>{s.model or 'gemini-2.5-flash'}</code>\n\n"
        f"{SEP}\n\n"
        f"<b>📨 So'rovlar (bugun):{warn_req}</b>\n"
        f"  Ishlatildi:  <b>{s.requests}</b> / 500\n"
        f"  Qoldi:       <b>{s.req_remaining}</b>\n"
        f"  <code>{_pct_bar(s.req_pct)}</code>  {s.req_pct:.1f}%\n\n"
        f"<b>🔤 Tokenlar (bugun):{warn_tok}</b>\n"
        f"  Prompt:  <b>{s.prompt_tokens:,}</b>\n"
        f"  Javob:   <b>{s.response_tokens:,}</b>\n"
        f"  Jami:    <b>{s.total_tokens:,}</b> / 1 000 000\n"
        f"  Qoldi:   <b>{s.tok_remaining:,}</b>\n"
        f"  <code>{_pct_bar(s.tok_pct)}</code>  {s.tok_pct:.1f}%\n\n"
        f"{SEP}\n\n"
        f"<b>⚡ Joriy sessiya:</b>\n"
        f"  So'rovlar: <b>{sess_req}</b>\n"
        f"  Tokenlar:  <b>{sess_tok:,}</b>"
    )

    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔄 Yangilash", callback_data="adm:gemini"))
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=b.as_markup())
    await callback.answer()


# ── 📡 Majburiy kanallar ───────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:channels")
async def adm_channels(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await state.clear()
    text, kb = await _fetch_channels_list()
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@sync_to_async
def _fetch_channels_list() -> tuple[str, InlineKeyboardMarkup]:
    channels = list(RequiredChannel.objects.all())
    b = InlineKeyboardBuilder()

    if not channels:
        text = (
            f"📡 <b>Majburiy kanallar</b>\n{SEP}\n\n"
            "Hozircha hech qanday majburiy kanal yo'q.\n\n"
            "<i>Kanal qo'shsangiz, foydalanuvchilar botdan foydalanishdan\n"
            "oldin o'sha kanallarga obuna bo'lishi shart bo'ladi.</i>"
        )
    else:
        lines = [f"📡 <b>Majburiy kanallar</b>  ({len(channels)} ta)\n{SEP}\n"]
        for i, ch in enumerate(channels, 1):
            tag = f"@{ch.username}" if ch.username else f"ID: {ch.channel_id}"
            status = "✅ Faol" if ch.is_active else "⏸ To'xtatilgan"
            lines.append(f"{i}. <b>{ch.title}</b>\n   {tag}  •  {status}")
        text = "\n".join(lines)
        for ch in channels:
            tog_icon = "⏸" if ch.is_active else "▶️"
            b.row(
                InlineKeyboardButton(
                    text=f"{'✅' if ch.is_active else '⏸'} {ch.title[:22]}",
                    callback_data=f"adm:ch_tog:{ch.id}",
                ),
                InlineKeyboardButton(text="🗑", callback_data=f"adm:ch_del:{ch.id}"),
            )

    b.row(
        InlineKeyboardButton(text="🌐 Public kanal qo'shish", callback_data="adm:ch_type:pub"),
        InlineKeyboardButton(text="🔒 Private kanal", callback_data="adm:ch_type:priv"),
    )
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))
    return text, b.as_markup()


# ── Kanal qo'shish: public (@username) ────────────────────────────────────────

@router.callback_query(F.data == "adm:ch_type:pub")
async def adm_ch_add_pub(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(ChannelAddState.waiting_username)
    await _safe_edit(
        callback,
        f"🌐 <b>Public kanal qo'shish</b>\n{SEP}\n\n"
        "Kanalning <b>@username</b> ini yuboring.\n\n"
        "<b>Misol:</b> <code>@mening_kanalim</code>\n\n"
        "⚠️ Bot kanalda <b>admin</b> bo'lishi kerak.",
        parse_mode="HTML",
        reply_markup=_back_kb("adm:channels"),
    )
    await callback.answer()


@router.message(ChannelAddState.waiting_username)
async def adm_ch_receive_username(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    username = (message.text or "").strip().lstrip("@")
    if not username:
        await message.answer("⚠️ @username kiriting.")
        return

    bot: Bot = message.bot
    wait_msg = await message.answer("⏳ Kanal tekshirilmoqda...")
    try:
        chat = await bot.get_chat(f"@{username}")
    except Exception as e:
        await wait_msg.edit_text(
            f"❌ Kanal topilmadi: <code>{e}</code>\n\n"
            "Bot kanalda admin bo'lishi va kanal public bo'lishi kerak.",
            parse_mode="HTML",
        )
        return

    if chat.type not in ("channel", "supergroup"):
        await wait_msg.edit_text("❌ Bu kanal yoki guruh emas.")
        return

    await state.clear()
    ch, created = await RequiredChannel.objects.aupdate_or_create(
        channel_id=chat.id,
        defaults={
            "username": username,
            "title": chat.title or f"@{username}",
            "invite_link": "",
            "is_active": True,
        },
    )
    action = "qo'shildi ✅" if created else "yangilandi 🔄"
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📡 Kanallar ro'yxati", callback_data="adm:channels"))
    b.row(InlineKeyboardButton(text="🏠 Admin panel", callback_data="adm:menu"))
    await wait_msg.edit_text(
        f"📡 <b>Kanal {action}</b>\n{SEP}\n\n"
        f"📛 Nomi:     <b>{ch.title}</b>\n"
        f"🔗 Username: @{ch.username}\n"
        f"🆔 ID:       <code>{ch.channel_id}</code>",
        parse_mode="HTML",
        reply_markup=b.as_markup(),
    )


# ── Kanal qo'shish: private (ID + invite link) ─────────────────────────────────

@router.callback_query(F.data == "adm:ch_type:priv")
async def adm_ch_add_priv(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await state.set_state(ChannelAddState.waiting_channel_id)
    await _safe_edit(
        callback,
        f"🔒 <b>Private kanal qo'shish</b>\n{SEP}\n\n"
        "Kanalning <b>ID</b> sini yuboring.\n\n"
        "<b>ID ni qanday topish:</b>\n"
        "1. Botni kanalga admin qo'shing\n"
        "2. Kanalga istalgan xabar yuboring\n"
        "3. @userinfobot ga forward qiling — ID ko'rinadi\n\n"
        "<b>Misol:</b> <code>-1001234567890</code>",
        parse_mode="HTML",
        reply_markup=_back_kb("adm:channels"),
    )
    await callback.answer()


@router.message(ChannelAddState.waiting_channel_id)
async def adm_ch_receive_id(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    raw = (message.text or "").strip()
    if not raw.lstrip("-").isdigit():
        await message.answer("❌ Faqat raqam kiriting. Misol: <code>-1001234567890</code>", parse_mode="HTML")
        return

    channel_id = int(raw)
    bot: Bot = message.bot
    wait_msg = await message.answer("⏳ Kanal tekshirilmoqda...")
    try:
        chat = await bot.get_chat(channel_id)
        title = chat.title or str(channel_id)
    except Exception as e:
        title = None
        await wait_msg.edit_text(
            f"⚠️ Kanal topilmadi: <code>{e}</code>\n\n"
            "Davom etish uchun invite link ni yuboring:",
            parse_mode="HTML",
        )

    if title:
        await wait_msg.edit_text(
            f"✅ Kanal topildi: <b>{title}</b>\n\n"
            "Endi kanal <b>invite havolasini</b> yuboring.\n"
            "<b>Misol:</b> <code>https://t.me/+xxxxxxxxxxxxxx</code>",
            parse_mode="HTML",
        )

    await state.update_data(channel_id=channel_id, title=title or str(channel_id))
    await state.set_state(ChannelAddState.waiting_invite_link)


@router.message(ChannelAddState.waiting_invite_link)
async def adm_ch_receive_invite(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    invite = (message.text or "").strip()
    if not invite.startswith("https://t.me/"):
        await message.answer(
            "❌ Noto'g'ri havola. Misol: <code>https://t.me/+xxxxxxxxxxxxxx</code>",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    channel_id = data["channel_id"]
    title = data["title"]
    await state.clear()

    ch, created = await RequiredChannel.objects.aupdate_or_create(
        channel_id=channel_id,
        defaults={
            "username": "",
            "title": title,
            "invite_link": invite,
            "is_active": True,
        },
    )
    action = "qo'shildi ✅" if created else "yangilandi 🔄"
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📡 Kanallar ro'yxati", callback_data="adm:channels"))
    b.row(InlineKeyboardButton(text="🏠 Admin panel", callback_data="adm:menu"))
    await message.answer(
        f"📡 <b>Kanal {action}</b>\n{SEP}\n\n"
        f"📛 Nomi:  <b>{ch.title}</b>\n"
        f"🆔 ID:    <code>{ch.channel_id}</code>\n"
        f"🔗 Link:  {ch.invite_link}",
        parse_mode="HTML",
        reply_markup=b.as_markup(),
    )


# ── Kanal toggle (faol/nofaol) ─────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^adm:ch_tog:\d+$"))
async def adm_ch_toggle(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    ch_id = int(callback.data.split(":")[2])
    ch = await RequiredChannel.objects.aget(id=ch_id)
    ch.is_active = not ch.is_active
    await ch.asave(update_fields=["is_active"])
    status = "faollashtirildi ✅" if ch.is_active else "to'xtatildi ⏸"
    await callback.answer(f"{ch.title} {status}", show_alert=True)
    text, kb = await _fetch_channels_list()
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=kb)


# ── Kanal o'chirish ────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^adm:ch_del:\d+$"))
async def adm_ch_del_ask(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    ch_id = int(callback.data.split(":")[2])
    try:
        ch = await RequiredChannel.objects.aget(id=ch_id)
    except RequiredChannel.DoesNotExist:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🗑 Ha, o'chirish", callback_data=f"adm:ch_del_ok:{ch_id}"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="adm:channels"),
    )
    await _safe_edit(
        callback,
        f"⚠️ <b>Kanalni o'chirish</b>\n{SEP}\n\n"
        f"<b>{ch.title}</b> kanalini majburiy obunalar ro'yxatidan\n"
        "o'chirmoqchimisiz?\n\n"
        "<i>Foydalanuvchilar endi bu kanalga obuna bo'lishi shart bo'lmaydi.</i>",
        parse_mode="HTML",
        reply_markup=b.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^adm:ch_del_ok:\d+$"))
async def adm_ch_del_confirm(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    ch_id = int(callback.data.split(":")[2])
    try:
        ch = await RequiredChannel.objects.aget(id=ch_id)
        title = ch.title
        await ch.adelete()
        await callback.answer(f"✅ «{title}» o'chirildi", show_alert=True)
    except RequiredChannel.DoesNotExist:
        await callback.answer("❌ Topilmadi", show_alert=True)
    text, kb = await _fetch_channels_list()
    await _safe_edit(callback, text, parse_mode="HTML", reply_markup=kb)