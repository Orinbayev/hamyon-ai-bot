"""
Report service — premium finance assistant uslubidagi hisobotlar.
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from asgiref.sync import sync_to_async
from django.db.models import Count, Sum

from apps.transactions.models import Transaction
from apps.users.models import TelegramUser

logger = logging.getLogger("services")

SEP = "━" * 15

CAT_ICONS = {
    "ovqat": "🍽", "taxi": "🚕", "transport": "🚌",
    "kiyim": "👗", "internet": "🌐", "telefon": "📱",
    "uy": "🏠", "kommunal": "💡", "oqish": "📚",
    "salomatlik": "💊", "kongilochar": "🎭", "ish_haqi": "💼",
    "qarz": "🤝", "sovga": "🎁", "boshqa": "📌",
}

MONTHS_UZ = {
    1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
    5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
    9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr",
}

DAYS_UZ = {
    0: "Dushanba", 1: "Seshanba", 2: "Chorshanba",
    3: "Payshanba", 4: "Juma", 5: "Shanba", 6: "Yakshanba",
}


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


def _stats(user, start, end):
    qs = Transaction.objects.filter(user=user, transaction_date__range=(start, end))
    income = qs.filter(type="income").aggregate(t=Sum("amount"))["t"] or Decimal("0")
    expense = qs.filter(type="expense").aggregate(t=Sum("amount"))["t"] or Decimal("0")
    cats = list(
        qs.filter(type="expense")
        .values("category__name", "category__slug")
        .annotate(total=Sum("amount"), cnt=Count("id"))
        .order_by("-total")
    )
    return income, expense, income - expense, cats, qs.count()


# ── Hisobotlar ───────────────────────────────────────────────────────────────

def _today(user: TelegramUser) -> str:
    today = date.today()
    month = MONTHS_UZ[today.month]
    day_name = DAYS_UZ[today.weekday()]
    income, expense, balance, cats, cnt = _stats(user, today, today)

    if cnt == 0:
        return (
            f"📅 <b>Bugun</b> — {today.day} {month}, {day_name}\n\n"
            f"Bugun hali hech narsa yozilmagan.\n\n"
            f"Xarajat yoki kirimni yozing."
        )

    lines = [
        f"📅 <b>Bugun</b> — {today.day} {month}, {day_name}",
        SEP,
        f"💰 Kirim:\n{_fmt(income)}",
        "",
        f"💸 Chiqim:\n{_fmt(expense)}",
        "",
        f"📈 Balans:\n{_signed(balance)}",
    ]

    if cats:
        lines += ["", SEP, "📊 <b>Xarajatlar</b>", ""]
        for c in cats[:6]:
            slug = c.get("category__slug") or "boshqa"
            name = c.get("category__name") or "Boshqa"
            icon = CAT_ICONS.get(slug, "📌")
            lines.append(f"{icon} {name} — {_fmt(c['total'])}")

    return "\n".join(lines)


def _week(user: TelegramUser) -> str:
    today = date.today()
    start = today - timedelta(days=today.weekday())
    income, expense, balance, cats, cnt = _stats(user, start, today)

    period = f"{start.day} {MONTHS_UZ[start.month]} – {today.day} {MONTHS_UZ[today.month]}"

    if cnt == 0:
        return (
            f"📆 <b>Bu hafta</b>\n{period}\n\n"
            f"Bu hafta hali hech narsa yozilmagan."
        )

    lines = [
        f"📆 <b>Bu hafta</b>",
        period,
        SEP,
        f"💰 Kirim:       {_fmt(income)}",
        f"💸 Chiqim:      {_fmt(expense)}",
        f"📈 Balans:      {_signed(balance)}",
        f"📝 Yozuvlar:    {cnt} ta",
    ]

    if cats:
        lines += ["", SEP, "📊 <b>Xarajatlar</b>", ""]
        for c in cats[:5]:
            slug = c.get("category__slug") or "boshqa"
            name = c.get("category__name") or "Boshqa"
            icon = CAT_ICONS.get(slug, "📌")
            pct = float(c["total"] / expense * 100) if expense else 0
            lines.append(f"{icon} {name}")
            lines.append(f"   {_fmt(c['total'])}  •  {pct:.0f}%")
            lines.append("")

    return "\n".join(lines).rstrip()


def _month(user: TelegramUser) -> str:
    today = date.today()
    start = today.replace(day=1)
    income, expense, balance, cats, cnt = _stats(user, start, today)

    month_name = f"{MONTHS_UZ[today.month]} {today.year}"

    if cnt == 0:
        return (
            f"📊 <b>{month_name}</b> — Oylik hisobot\n\n"
            f"Bu oy hali hech narsa yozilmagan."
        )

    lines = [
        f"📊 <b>{month_name}</b> — Oylik hisobot",
        SEP,
        f"💰 Jami kirim:\n{_fmt(income)}",
        "",
        f"💸 Jami chiqim:\n{_fmt(expense)}",
        "",
        f"📈 Sof foyda:\n{_signed(balance)}",
    ]

    if cats:
        top_amount = cats[0]
        top_count = max(cats, key=lambda c: c["cnt"])

        top_name = top_amount.get("category__name") or "Boshqa"
        top_icon = CAT_ICONS.get(top_amount.get("category__slug") or "boshqa", "📌")
        active_name = top_count.get("category__name") or "Boshqa"

        lines += [
            "",
            SEP,
            f"🔥 Eng katta xarajat:",
            f"{top_icon} {top_name} — {_fmt(top_amount['total'])}",
            "",
            f"📊 Eng faol kategoriya:",
            f"{active_name} — {top_count['cnt']} ta yozuv",
            "",
            SEP,
            "📋 <b>Xarajat taqsimoti</b>",
            "",
        ]
        for c in cats:
            slug = c.get("category__slug") or "boshqa"
            name = c.get("category__name") or "Boshqa"
            icon = CAT_ICONS.get(slug, "📌")
            pct = float(c["total"] / expense * 100) if expense else 0
            lines.append(f"{icon} {name}")
            lines.append(f"   {_fmt(c['total'])}  •  {pct:.0f}%  •  {c['cnt']} ta")
            lines.append("")

    return "\n".join(lines).rstrip()


def _balance(user: TelegramUser) -> str:
    today = date.today()
    all_inc, all_exp, all_bal, _, _ = _stats(user, date(2000, 1, 1), today)
    d_inc, d_exp, d_bal, _, _ = _stats(user, today, today)
    w_inc, w_exp, w_bal, _, _ = _stats(user, today - timedelta(days=today.weekday()), today)
    m_inc, m_exp, m_bal, _, _ = _stats(user, today.replace(day=1), today)

    return (
        f"💰 <b>Umumiy balans</b>\n"
        f"{SEP}\n"
        f"Jami kirim:    {_fmt(all_inc)}\n"
        f"Jami chiqim:   {_fmt(all_exp)}\n\n"
        f"Sof balans:\n"
        f"<b>{_signed(all_bal)}</b>\n"
        f"{SEP}\n"
        f"📅 <b>Bugun</b>\n"
        f"• Kirim:    {_fmt(d_inc)}\n"
        f"• Chiqim:   {_fmt(d_exp)}\n"
        f"• Balans:   {_signed(d_bal)}\n"
        f"{SEP}\n"
        f"📆 <b>Bu hafta</b>\n"
        f"• Kirim:    {_fmt(w_inc)}\n"
        f"• Chiqim:   {_fmt(w_exp)}\n"
        f"• Balans:   {_signed(w_bal)}\n"
        f"{SEP}\n"
        f"🗓 <b>Bu oy</b>\n"
        f"• Kirim:    {_fmt(m_inc)}\n"
        f"• Chiqim:   {_fmt(m_exp)}\n"
        f"• Balans:   {_signed(m_bal)}"
    )


def _categories(user: TelegramUser) -> str:
    today = date.today()
    start = today.replace(day=1)
    month_name = f"{MONTHS_UZ[today.month]} {today.year}"

    qs = Transaction.objects.filter(user=user, type="expense", transaction_date__gte=start)
    total = qs.aggregate(t=Sum("amount"))["t"] or Decimal("0")
    cats = list(
        qs.values("category__name", "category__slug")
        .annotate(total=Sum("amount"), cnt=Count("id"))
        .order_by("-total")
    )

    if not cats:
        return (
            f"📊 <b>Kategoriyalar</b> — {month_name}\n\n"
            f"Bu oy hali xarajat yozilmagan."
        )

    lines = [
        f"📊 <b>Kategoriyalar</b> — {month_name}",
        f"Jami chiqim: <b>{_fmt(total)}</b>",
        SEP,
    ]
    for c in cats:
        slug = c.get("category__slug") or "boshqa"
        name = c.get("category__name") or "Boshqa"
        icon = CAT_ICONS.get(slug, "📌")
        pct = float(c["total"] / total * 100) if total else 0
        lines.append(f"\n{icon} <b>{name}</b>")
        lines.append(f"   {_fmt(c['total'])}  •  {pct:.0f}%  •  {c['cnt']} ta")

    return "\n".join(lines)


def _history_text(txs: list, limit: int = 20) -> str:
    if not txs:
        return f"📋 <b>Tarix</b>\n{SEP}\n\nHali hech narsa yozilmagan."
    lines = [f"📋 <b>Oxirgi {len(txs)} ta yozuv</b>", SEP]
    prev_date = None
    for t in txs:
        if t.transaction_date != prev_date:
            d = t.transaction_date
            lines.append(f"\n<b>{d.day} {MONTHS_UZ[d.month]}</b>")
            prev_date = t.transaction_date
        icon = "💰" if t.type == "income" else "💸"
        cat_name = t.category.name if t.category else "Boshqa"
        slug = t.category.slug if t.category else "boshqa"
        cat_icon = CAT_ICONS.get(slug, "📌")
        sign = "+" if t.type == "income" else "–"
        note = f"  · {t.note}" if t.note else ""
        lines.append(
            f"  {icon} {cat_icon} {cat_name}"
            f"   {sign}{_fmt(t.amount, t.currency)}"
            f"  <code>#{t.id}</code>{note}"
        )
    lines.append(f"\n{SEP}\n🗑 O'chirish: /delete yoki /delete {txs[-1].id}")
    return "\n".join(lines)


def _history(user: TelegramUser, limit: int = 20) -> str:
    txs = list(
        Transaction.objects.filter(user=user)
        .select_related("category")
        .order_by("-transaction_date", "-created_at")[:limit]
    )
    return _history_text(txs, limit)


def _history_with_txs(user: TelegramUser, limit: int = 20) -> tuple:
    txs = list(
        Transaction.objects.filter(user=user)
        .select_related("category")
        .order_by("-transaction_date", "-created_at")[:limit]
    )
    return _history_text(txs, limit), txs


def _period_stats(user: TelegramUser, start: date, end: date) -> dict:
    qs = Transaction.objects.filter(user=user, transaction_date__range=(start, end))
    income = qs.filter(type="income").aggregate(t=Sum("amount"))["t"] or Decimal("0")
    expense = qs.filter(type="expense").aggregate(t=Sum("amount"))["t"] or Decimal("0")
    cats = list(
        qs.filter(type="expense")
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")[:3]
    )
    return {
        "income": income,
        "expense": expense,
        "balance": income - expense,
        "count": qs.count(),
        "top_cats": cats,
    }


# ── Async public API ─────────────────────────────────────────────────────────

build_today_report = sync_to_async(_today)
build_week_report = sync_to_async(_week)
build_month_report = sync_to_async(_month)
build_balance_report = sync_to_async(_balance)
build_categories_report = sync_to_async(_categories)
build_history = sync_to_async(_history)
build_history_with_txs = sync_to_async(_history_with_txs)
get_period_stats = sync_to_async(_period_stats)
