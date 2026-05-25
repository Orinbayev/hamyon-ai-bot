"""
Matnli xabarlar handleri.
Flow: Handler → Service → Repository → DB
Engagement (streak/level) har saqlash keyin hisoblanadi.
"""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.parser import AIParser
from app.bot.keyboards.inline import confirm_transactions_keyboard
from app.bot.keyboards.reply import MENU_BUTTONS, main_menu
from app.bot.states.onboarding import OnboardingState
from app.models.transaction import Transaction
from app.models.user import User
from app.repositories.category_repo import CategoryRepository
from app.repositories.transaction_repo import TransactionRepository
from app.schemas.transaction import TransactionItem
from app.services.engagement_service import EngagementResult, EngagementService
from app.services.transaction_service import TransactionService
from app.utils.formatters import (
    CAT_NAMES, PAYMENT_LABELS, NUM_EMOJIS, SEP,
    fmt_amount, fmt_date, fmt_signed,
)
from app.utils.motivational import get_message

logger = logging.getLogger("bot.message")
router = Router(name="message")


def _make_services(session: AsyncSession) -> tuple[TransactionService, EngagementService]:
    return (
        TransactionService(TransactionRepository(session), CategoryRepository(session)),
        EngagementService(session),
    )


def _preview(items: list[TransactionItem]) -> str:
    lines = []
    for i, item in enumerate(items):
        num = NUM_EMOJIS[i] if i < len(NUM_EMOJIS) else f"{i + 1}."
        t_icon = "💰" if item.type == "income" else "💸"
        cat_name = CAT_NAMES.get(item.category, "Boshqa")
        lines.append(
            f"{num} {t_icon} {cat_name} — {fmt_amount(item.amount, item.currency)}"
            f"  •  {fmt_date(item.date)}"
            + (f"  · {item.note}" if item.note else "")
        )
    return "\n".join(lines)


async def _build_reply(
    user: User,
    items: list[TransactionItem],
    saved: list[Transaction],
    engagement: EngagementResult,
    session: AsyncSession,
) -> str:
    if not saved:
        return "❌ Saqlashda xato yuz berdi. Qayta urinib ko'ring."

    name = engagement.name

    # ── Today's stats footer ──────────────────────────────────────────────────
    from datetime import date as _date
    today = _date.today()
    tx_repo = TransactionRepository(session)

    from app.models.transaction import TransactionType
    inc = await tx_repo.get_sum_for_user(user.id, today, today, TransactionType.INCOME)
    exp = await tx_repo.get_sum_for_user(user.id, today, today, TransactionType.EXPENSE)
    bal = inc - exp

    stats_block = (
        f"{SEP}\n"
        f"📊 Bugungi statistika\n\n"
        f"• Jami chiqim:  {fmt_amount(exp)}\n"
        f"• Jami kirim:   {fmt_amount(inc)}\n"
        f"• Balans:       {fmt_signed(bal)}"
    )

    # ── Single transaction ────────────────────────────────────────────────────
    if len(saved) == 1:
        item = items[0]
        is_expense = item.type == "expense"
        amount_str = fmt_amount(item.amount, item.currency)
        cat_name = CAT_NAMES.get(item.category, "Boshqa")
        payment = PAYMENT_LABELS.get(item.payment_method, "Naqd pul")
        date_label = fmt_date(item.date)

        if is_expense:
            header = f"✅ Xarajat saqlandi, {name}!"
            amount_line = f"💸 Summa: <b>{amount_str}</b>"
            cat_line = f"📌 Kategoriya: {cat_name}"
        else:
            header = f"✅ Kirim saqlandi, {name}!"
            amount_line = f"💰 Summa: <b>{amount_str}</b>"
            cat_line = f"📌 Manba: {cat_name}"

        lines = [
            header, "",
            amount_line, cat_line,
            f"💳 To'lov turi: {payment}",
            f"📅 Sana: {date_label}",
        ]
        if item.note:
            lines.append(f"📝 Izoh: {item.note}")

        lines += ["", engagement.motivational_msg, "", stats_block]

        # Streak or level-up bonus
        if engagement.bonus_msg:
            lines += ["", engagement.bonus_msg]

        # "Almost there" hint
        hint = engagement.next_streak_hint
        if hint:
            lines += ["", hint]

        return "\n".join(lines)

    # ── Multiple transactions ─────────────────────────────────────────────────
    num_exp = sum(1 for i in items if i.type == "expense")
    count = len(saved)

    if num_exp == count:
        context = "save_multi"
        header = f"✅ {count} ta xarajat saqlandi, {name}!"
    elif num_exp == 0:
        context = "save_multi"
        header = f"✅ {count} ta kirim saqlandi, {name}!"
    else:
        context = "save_multi"
        header = f"✅ {count} ta yozuv saqlandi, {name}!"

    lines = [header, "", get_message(context, name, count=count), ""]
    for idx, item in enumerate(items[:9]):
        num = NUM_EMOJIS[idx] if idx < len(NUM_EMOJIS) else f"{idx + 1}."
        cat_name = CAT_NAMES.get(item.category, "Boshqa")
        lines.append(f"{num} {cat_name} — {fmt_amount(item.amount, item.currency)}")

    if len(items) > 9:
        lines.append(f"... va yana {len(items) - 9} ta")

    lines += ["", stats_block]
    if engagement.bonus_msg:
        lines += ["", engagement.bonus_msg]

    return "\n".join(lines)


# ── Handlers ──────────────────────────────────────────────────────────────────

@router.message(
    F.text
    & ~F.text.startswith("/")
    & ~F.text.in_(MENU_BUTTONS),
    ~OnboardingState.waiting_for_name,
)
async def handle_text(
    message: Message,
    user: User,
    user_id: int,
    session: AsyncSession,
    state: FSMContext,
    ai_parser: AIParser,
) -> None:
    text = message.text.strip()
    thinking = await message.answer("⏳ Tahlil qilinmoqda...")

    try:
        items = await ai_parser.parse_text(text)
    except Exception:
        await thinking.delete()
        await message.answer(
            "❌ AI xizmati bilan bog'lanishda xato\n\nIltimos, bir ozdan keyin qayta urinib ko'ring.",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )
        return

    await thinking.delete()

    if not items:
        await message.answer(
            f"⚠️ Xabar tushunilmadi, {user.display_name}\n\n"
            "Iltimos aniqroq yozing:\n"
            "• summa\n• kirim yoki chiqim\n• kategoriya\n\n"
            "Misol:\n<i>\"Taxi uchun 25 ming ketdi\"</i>",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )
        return

    tx_svc, eng_svc = _make_services(session)
    context = "save_income" if all(i.type == "income" for i in items) else "save_expense"
    if len(items) > 1:
        context = "save_multi"

    if len(items) == 1:
        saved = await tx_svc.save_from_ai(user_id, items, text)
        engagement = await eng_svc.record_activity(user, context=context, count=len(saved))
        reply = await _build_reply(user, items, saved, engagement, session)
        await message.answer(reply, parse_mode="HTML", reply_markup=main_menu())
        return

    # Multiple — confirm first
    await state.update_data(
        pending_items=[i.model_dump(mode="json") for i in items],
        raw_text=text,
    )
    await message.answer(
        f"📋 <b>{len(items)} ta tranzaksiya topildi, {user.display_name}:</b>\n\n"
        f"{_preview(items)}\n\n{SEP}\n"
        "Hammasini saqlashni tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=confirm_transactions_keyboard(len(items)),
    )


@router.callback_query(F.data == "confirm_save")
async def confirm_save(
    callback: CallbackQuery,
    user: User,
    user_id: int,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    data = await state.get_data()
    raw_items = data.get("pending_items", [])
    raw_text = data.get("raw_text", "")
    await state.clear()

    if not raw_items:
        await callback.answer("Saqlash uchun ma'lumot topilmadi.", show_alert=True)
        return

    items = [TransactionItem.model_validate(i) for i in raw_items]
    tx_svc, eng_svc = _make_services(session)
    saved = await tx_svc.save_from_ai(user_id, items, raw_text)
    engagement = await eng_svc.record_activity(user, context="save_multi", count=len(saved))
    reply = await _build_reply(user, items, saved, engagement, session)

    await callback.message.edit_text(reply, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "cancel_save")
async def cancel_save(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi")
    await callback.answer()
