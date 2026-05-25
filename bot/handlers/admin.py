"""
Admin panel handler.
Faqat settings.ADMIN_IDS ro'yxatidagi Telegram ID larga ruxsat beriladi.

Features:
  📊 Umumiy statistika — barcha foydalanuvchilar bo'yicha yig'ilgan ma'lumot
  👥 Foydalanuvchilar  — sahifalangan ro'yxat, har birini bosib detail ko'rish
  👤 User detail       — statistika, oxirgi 5 tranzaksiya, excel eksport, tozalash
  📢 Xabar yuborish    — barcha faol foydalanuvchilarga broadcast
  ℹ️ Bot haqida        — bugungi/haftalik o'sish, TOP-3 faol
  /whoami              — o'z Telegram ID ni ko'rish (admin qo'shish uchun)
"""

import asyncio
import logging
from datetime import date, timedelta

from aiogram import Bot, F, Router
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
from apps.users.models import TelegramUser
from services import export as export_service
from services.token_tracker import tracker as gemini_tracker

logger = logging.getLogger("bot.admin")
router = Router(name="admin")

SEP = "━" * 15
USERS_PER_PAGE = 8


class AdminState(StatesGroup):
    waiting_broadcast_text = State()
    confirm_broadcast = State()


# ── Access helpers ─────────────────────────────────────────────────────────────

def _is_admin(tg_id: int) -> bool:
    return tg_id in getattr(settings, "ADMIN_IDS", [])


# ── Keyboards ──────────────────────────────────────────────────────────────────

def _main_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📊 Statistika", callback_data="adm:stats"),
        InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="adm:users:0"),
    )
    b.row(
        InlineKeyboardButton(text="📢 Xabar yuborish", callback_data="adm:broadcast"),
        InlineKeyboardButton(text="ℹ️ Bot haqida", callback_data="adm:about"),
    )
    b.row(InlineKeyboardButton(text="🤖 Gemini tokenlar", callback_data="adm:gemini"))
    return b.as_markup()


def _back_kb(target: str = "adm:menu") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=target))
    return b.as_markup()


# ── /whoami — o'z ID ni bilish ─────────────────────────────────────────────────

@router.message(Command("whoami"))
async def cmd_whoami(message: Message) -> None:
    await message.answer(
        f"🆔 Sizning Telegram ID: <code>{message.from_user.id}</code>\n\n"
        f"Admin qo'shish uchun bu raqamni <code>.env</code> faylidagi\n"
        f"<code>ADMIN_IDS=</code> qatoriga yozing.",
        parse_mode="HTML",
    )


# ── /admin command ─────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message, db_user: TelegramUser, state: FSMContext) -> None:
    await state.clear()
    if not _is_admin(message.from_user.id):
        return
    name = db_user.full_name.split()[0]
    await message.answer(
        f"🛠 <b>Admin panel</b>\n{SEP}\nXush kelibsiz, <b>{name}</b>!\n\nBo'limni tanlang:",
        parse_mode="HTML",
        reply_markup=_main_kb(),
    )


@router.callback_query(F.data == "adm:menu")
async def adm_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text(
        f"🛠 <b>Admin panel</b>\n{SEP}\nBo'limni tanlang:",
        parse_mode="HTML",
        reply_markup=_main_kb(),
    )
    await callback.answer()


# ── 📊 Stats ───────────────────────────────────────────────────────────────────

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

    total_users = TelegramUser.objects.count()
    active_today = (
        Transaction.objects.filter(transaction_date=today)
        .values("user_id").distinct().count()
    )
    active_week = (
        Transaction.objects.filter(transaction_date__gte=week_ago)
        .values("user_id").distinct().count()
    )
    total_tx = Transaction.objects.count()

    agg = Transaction.objects.aggregate(
        income=Coalesce(
            Sum("amount", filter=Q(type="income")), Value(0), output_field=DecimalField()
        ),
        expense=Coalesce(
            Sum("amount", filter=Q(type="expense")), Value(0), output_field=DecimalField()
        ),
    )
    income = float(agg["income"])
    expense = float(agg["expense"])
    balance = income - expense

    def fu(v):
        return f"{v:,.0f}".replace(",", " ") + " so'm"

    def fs(v):
        s = "+" if v >= 0 else "–"
        return f"{s}{abs(v):,.0f}".replace(",", " ") + " so'm"

    return (
        f"📊 <b>Umumiy statistika</b>\n{SEP}\n\n"
        f"👥 Jami foydalanuvchilar:   <b>{total_users}</b>\n"
        f"🟢 Faol (bu hafta):          <b>{active_week}</b>\n"
        f"🟡 Faol (bugun):             <b>{active_today}</b>\n\n"
        f"{SEP}\n\n"
        f"📋 Jami tranzaksiyalar:     <b>{total_tx}</b>\n"
        f"💰 Jami kirim:              <b>{fu(income)}</b>\n"
        f"💸 Jami chiqim:             <b>{fu(expense)}</b>\n"
        f"📈 Umumiy balans:           <b>{fs(balance)}</b>"
    )


# ── 👥 User list ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm:users:"))
async def adm_users(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    page = int(callback.data.split(":")[2])
    text, kb = await _fetch_users_page(page)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


@sync_to_async
def _fetch_users_page(page: int) -> tuple[str, InlineKeyboardMarkup]:
    total = TelegramUser.objects.count()
    offset = page * USERS_PER_PAGE

    users = list(
        TelegramUser.objects
        .annotate(
            _tx=Count("transactions"),
            _exp=Coalesce(
                Sum("transactions__amount", filter=Q(transactions__type="expense")),
                Value(0), output_field=DecimalField(),
            ),
        )
        .order_by("-_tx")[offset:offset + USERS_PER_PAGE]
    )

    start_n = offset + 1
    end_n = min(offset + USERS_PER_PAGE, total)
    lines = [f"👥 <b>Foydalanuvchilar</b>  {start_n}–{end_n} / {total}\n{SEP}\n"]
    for i, u in enumerate(users, start_n):
        uname = f"@{u.username}" if u.username else "—"
        exp_str = f"{float(u._exp):,.0f}".replace(",", " ")
        lines.append(
            f"{i}. <b>{u.full_name}</b>  {uname}\n"
            f"   📋 {u._tx} ta  •  💸 {exp_str} so'm\n"
        )

    b = InlineKeyboardBuilder()
    for u in users:
        b.row(InlineKeyboardButton(
            text=f"👤 {u.full_name[:28]}",
            callback_data=f"adm:user:{u.id}",
        ))

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"adm:users:{page - 1}"))
    if end_n < total:
        nav.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"adm:users:{page + 1}"))
    if nav:
        b.row(*nav)
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:menu"))

    return "\n".join(lines), b.as_markup()


# ── 👤 User detail ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm:user:"))
async def adm_user_detail(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    text, kb = await _fetch_user_detail(user_id)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
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
    balance = income - expense

    last_txs = list(
        Transaction.objects.filter(user=u)
        .select_related("category")
        .order_by("-transaction_date", "-created_at")[:5]
    )

    uname = f"@{u.username}" if u.username else "—"

    def fu(v):
        return f"{v:,.0f}".replace(",", " ") + " so'm"

    def fs(v):
        s = "+" if v >= 0 else "–"
        return f"{s}{abs(v):,.0f}".replace(",", " ") + " so'm"

    lines = [
        f"👤 <b>{u.full_name}</b>  {uname}\n{SEP}\n",
        f"🆔 Telegram ID:    <code>{u.telegram_id}</code>",
        f"📅 Ro'yxatdan:     {u.created_at.strftime('%d.%m.%Y')}",
        f"🟢 Holat:          {'Faol ✅' if u.is_active else 'Nofaol ❌'}\n",
        f"📋 Tranzaksiyalar: <b>{agg['total']}</b>",
        f"💰 Kirim:          <b>{fu(income)}</b>",
        f"💸 Chiqim:         <b>{fu(expense)}</b>",
        f"📈 Balans:         <b>{fs(balance)}</b>",
    ]

    if last_txs:
        lines.append(f"\n{SEP}\n🕐 Oxirgi {len(last_txs)} ta:\n")
        nums = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        for i, t in enumerate(last_txs):
            icon = "💰" if t.type == "income" else "💸"
            cat = t.category.name if t.category else "Boshqa"
            amt = f"{float(t.amount):,.0f}".replace(",", " ")
            lines.append(
                f"{nums[i]} {icon} {cat} — {amt} {t.currency}"
                f"  ({t.transaction_date.strftime('%d.%m')})"
            )

    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📊 Excel eksport", callback_data=f"adm:export:{u.id}"),
        InlineKeyboardButton(text="🗑 Tarixni tozalash", callback_data=f"adm:clear:{u.id}"),
    )
    b.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm:users:0"))

    return "\n".join(lines), b.as_markup()


# ── Admin: export user data as Excel ──────────────────────────────────────────

@router.callback_query(F.data.startswith("adm:export:"))
async def adm_export_user(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    try:
        u = await TelegramUser.objects.aget(id=user_id)
        file_bytes = await export_service.export_excel(u)
        today = date.today()
        doc = BufferedInputFile(
            file_bytes.read(),
            filename=f"user_{u.telegram_id}_{today}.xlsx",
        )
        await callback.message.answer_document(
            doc,
            caption=f"📊 <b>{u.full_name}</b> — barcha tranzaksiyalar",
            parse_mode="HTML",
        )
        await callback.answer("✅ Yuborildi")
    except Exception as e:
        logger.exception("Admin export xatosi: %s", e)
        await callback.answer("❌ Eksport xatosi", show_alert=True)


# ── Admin: clear user history ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm:clear:"))
async def adm_clear_ask(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🗑 Ha, tozalash", callback_data=f"adm:clear_ok:{user_id}"),
        InlineKeyboardButton(text="❌ Bekor", callback_data=f"adm:user:{user_id}"),
    )
    await callback.message.edit_text(
        f"⚠️ <b>Tarixni tozalash</b>\n{SEP}\n"
        "Bu foydalanuvchining barcha tranzaksiyalari o'chiriladi.\n\n"
        "Tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=b.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:clear_ok:"))
async def adm_clear_confirm(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    user_id = int(callback.data.split(":")[2])
    deleted, _ = await Transaction.objects.filter(user_id=user_id).adelete()
    await callback.message.edit_text(
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
    await callback.message.edit_text(
        f"📢 <b>Xabar yuborish</b>\n{SEP}\n"
        "Barcha faol foydalanuvchilarga yuboriladigan xabarni yozing:\n\n"
        "<i>HTML teglari ishlatiladi: &lt;b&gt;, &lt;i&gt;, &lt;code&gt;</i>",
        parse_mode="HTML",
        reply_markup=_back_kb("adm:menu"),
    )
    await callback.answer()


@router.message(AdminState.waiting_broadcast_text)
async def adm_broadcast_text(message: Message, state: FSMContext) -> None:
    if not _is_admin(message.from_user.id):
        return
    text = message.text or ""
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
        InlineKeyboardButton(text="✏️ Qayta yozish", callback_data="adm:broadcast"),
    )
    b.row(InlineKeyboardButton(text="❌ Bekor", callback_data="adm:menu"))

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
        if sent % 10 == 0:
            await asyncio.sleep(0.4)

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


# ── ℹ️ About ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:about")
async def adm_about(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):
        return
    text = await _fetch_about()
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_back_kb("adm:menu"))
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

    top = list(
        TelegramUser.objects
        .annotate(_tx=Count("transactions"))
        .order_by("-_tx")[:3]
    )
    medals = ["🥇", "🥈", "🥉"]
    top_lines = [
        f"{medals[i]} {u.full_name} — {u._tx} ta" for i, u in enumerate(top)
    ]

    return (
        f"ℹ️ <b>Bot haqida</b>\n{SEP}\n\n"
        f"📅 Bugun qo'shildi:    <b>{new_today}</b>\n"
        f"📆 Bu hafta:           <b>{new_week}</b>\n"
        f"🗓 Bu oy:              <b>{new_month}</b>\n\n"
        f"{SEP}\n\n"
        f"🏆 <b>TOP-3 faol foydalanuvchi:</b>\n"
        + "\n".join(top_lines)
    )


# ── 🤖 Gemini token stats ──────────────────────────────────────────────────────

def _pct_bar(pct: float, width: int = 12) -> str:
    filled = round(pct / 100 * width)
    return "▓" * filled + "░" * (width - filled)


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
        f"<b>📨 So'rovlar (bugun):</b>{warn_req}\n"
        f"  Ishlatildi:  <b>{s.requests}</b> / 500\n"
        f"  Qoldi:       <b>{s.req_remaining}</b>\n"
        f"  <code>{_pct_bar(s.req_pct)}</code>  {s.req_pct:.1f}%\n\n"
        f"<b>🔤 Tokenlar (bugun):</b>{warn_tok}\n"
        f"  Prompt:      <b>{s.prompt_tokens:,}</b>\n"
        f"  Javob:       <b>{s.response_tokens:,}</b>\n"
        f"  Jami:        <b>{s.total_tokens:,}</b> / 1 000 000\n"
        f"  Qoldi:       <b>{s.tok_remaining:,}</b>\n"
        f"  <code>{_pct_bar(s.tok_pct)}</code>  {s.tok_pct:.1f}%\n\n"
        f"{SEP}\n\n"
        f"<b>⚡ Joriy sessiya:</b>\n"
        f"  So'rovlar: <b>{sess_req}</b>\n"
        f"  Tokenlar:  <b>{sess_tok:,}</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=_back_kb("adm:menu"))
    await callback.answer()
