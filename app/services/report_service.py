from datetime import date, timedelta
from decimal import Decimal

from app.models.transaction import TransactionType
from app.repositories.transaction_repo import TransactionRepository
from app.utils.formatters import (
    CAT_ICONS,
    DAYS_UZ,
    MONTHS_UZ,
    SEP,
    fmt_amount,
    fmt_signed,
)


class ReportService:
    def __init__(self, transaction_repo: TransactionRepository) -> None:
        self.repo = transaction_repo

    # ── Internal ─────────────────────────────────────────────────────────────

    async def _stats(self, user_id: int, start: date, end: date) -> dict:
        income = await self.repo.get_sum_for_user(user_id, start, end, TransactionType.INCOME)
        expense = await self.repo.get_sum_for_user(user_id, start, end, TransactionType.EXPENSE)
        cats = await self.repo.get_category_stats_for_user(user_id, start, end)
        return {
            "income": income,
            "expense": expense,
            "balance": income - expense,
            "cats": cats,
        }

    # ── Public report methods ─────────────────────────────────────────────────

    async def today(self, user_id: int) -> str:
        today = date.today()
        s = await self._stats(user_id, today, today)
        month = MONTHS_UZ[today.month]
        day_name = DAYS_UZ[today.weekday()]

        if not s["cats"] and s["income"] == 0 and s["expense"] == 0:
            return (
                f"📅 <b>Bugun</b> — {today.day} {month}, {day_name}\n\n"
                "Bugun hali hech narsa yozilmagan.\n\nXarajat yoki kirimni yozing."
            )

        lines = [
            f"📅 <b>Bugun</b> — {today.day} {month}, {day_name}",
            SEP,
            f"💰 Kirim:\n{fmt_amount(s['income'])}",
            "",
            f"💸 Chiqim:\n{fmt_amount(s['expense'])}",
            "",
            f"📈 Balans:\n{fmt_signed(s['balance'])}",
        ]
        if s["cats"]:
            lines += ["", SEP, "📊 <b>Xarajatlar</b>", ""]
            for c in s["cats"][:6]:
                icon = CAT_ICONS.get(c["slug"], "📌")
                lines.append(f"{icon} {c['name']} — {fmt_amount(c['total'])}")
        return "\n".join(lines)

    async def week(self, user_id: int) -> str:
        today = date.today()
        start = today - timedelta(days=today.weekday())
        s = await self._stats(user_id, start, today)
        period = f"{start.day} {MONTHS_UZ[start.month]} – {today.day} {MONTHS_UZ[today.month]}"

        if not s["cats"] and s["income"] == 0 and s["expense"] == 0:
            return f"📆 <b>Bu hafta</b>\n{period}\n\nBu hafta hali hech narsa yozilmagan."

        txs = await self.repo.get_by_period_for_user(user_id, start, today)
        cnt = len(txs)

        lines = [
            "📆 <b>Bu hafta</b>",
            period,
            SEP,
            f"💰 Kirim:       {fmt_amount(s['income'])}",
            f"💸 Chiqim:      {fmt_amount(s['expense'])}",
            f"📈 Balans:      {fmt_signed(s['balance'])}",
            f"📝 Yozuvlar:    {cnt} ta",
        ]
        if s["cats"]:
            lines += ["", SEP, "📊 <b>Xarajatlar</b>", ""]
            for c in s["cats"][:5]:
                icon = CAT_ICONS.get(c["slug"], "📌")
                pct = float(c["total"] / s["expense"] * 100) if s["expense"] else 0
                lines.append(f"{icon} {c['name']}")
                lines.append(f"   {fmt_amount(c['total'])}  •  {pct:.0f}%")
                lines.append("")
        return "\n".join(lines).rstrip()

    async def month(self, user_id: int) -> str:
        today = date.today()
        start = today.replace(day=1)
        s = await self._stats(user_id, start, today)
        month_name = f"{MONTHS_UZ[today.month]} {today.year}"

        if not s["cats"] and s["income"] == 0 and s["expense"] == 0:
            return f"📊 <b>{month_name}</b> — Oylik hisobot\n\nBu oy hali hech narsa yozilmagan."

        lines = [
            f"📊 <b>{month_name}</b> — Oylik hisobot",
            SEP,
            f"💰 Jami kirim:\n{fmt_amount(s['income'])}",
            "",
            f"💸 Jami chiqim:\n{fmt_amount(s['expense'])}",
            "",
            f"📈 Sof foyda:\n{fmt_signed(s['balance'])}",
        ]
        if s["cats"]:
            top_a = s["cats"][0]
            top_c = max(s["cats"], key=lambda c: c["count"])
            top_icon = CAT_ICONS.get(top_a["slug"], "📌")
            lines += [
                "",
                SEP,
                "🔥 Eng katta xarajat:",
                f"{top_icon} {top_a['name']} — {fmt_amount(top_a['total'])}",
                "",
                "📊 Eng faol kategoriya:",
                f"{top_c['name']} — {top_c['count']} ta yozuv",
                "",
                SEP,
                "📋 <b>Xarajat taqsimoti</b>",
                "",
            ]
            for c in s["cats"]:
                icon = CAT_ICONS.get(c["slug"], "📌")
                pct = float(c["total"] / s["expense"] * 100) if s["expense"] else 0
                lines.append(f"{icon} {c['name']}")
                lines.append(f"   {fmt_amount(c['total'])}  •  {pct:.0f}%  •  {c['count']} ta")
                lines.append("")
        return "\n".join(lines).rstrip()

    async def balance(self, user_id: int) -> str:
        today = date.today()
        all_s = await self._stats(user_id, date(2000, 1, 1), today)
        d_s = await self._stats(user_id, today, today)
        w_s = await self._stats(user_id, today - timedelta(days=today.weekday()), today)
        m_s = await self._stats(user_id, today.replace(day=1), today)

        return (
            f"💰 <b>Umumiy balans</b>\n"
            f"{SEP}\n"
            f"Jami kirim:    {fmt_amount(all_s['income'])}\n"
            f"Jami chiqim:   {fmt_amount(all_s['expense'])}\n\n"
            f"Sof balans:\n"
            f"<b>{fmt_signed(all_s['balance'])}</b>\n"
            f"{SEP}\n"
            f"📅 <b>Bugun</b>\n"
            f"• Kirim:    {fmt_amount(d_s['income'])}\n"
            f"• Chiqim:   {fmt_amount(d_s['expense'])}\n"
            f"• Balans:   {fmt_signed(d_s['balance'])}\n"
            f"{SEP}\n"
            f"📆 <b>Bu hafta</b>\n"
            f"• Kirim:    {fmt_amount(w_s['income'])}\n"
            f"• Chiqim:   {fmt_amount(w_s['expense'])}\n"
            f"• Balans:   {fmt_signed(w_s['balance'])}\n"
            f"{SEP}\n"
            f"🗓 <b>Bu oy</b>\n"
            f"• Kirim:    {fmt_amount(m_s['income'])}\n"
            f"• Chiqim:   {fmt_amount(m_s['expense'])}\n"
            f"• Balans:   {fmt_signed(m_s['balance'])}"
        )

    async def categories(self, user_id: int) -> str:
        today = date.today()
        start = today.replace(day=1)
        month_name = f"{MONTHS_UZ[today.month]} {today.year}"
        s = await self._stats(user_id, start, today)

        if not s["cats"]:
            return f"📊 <b>Kategoriyalar</b> — {month_name}\n\nBu oy hali xarajat yozilmagan."

        lines = [
            f"📊 <b>Kategoriyalar</b> — {month_name}",
            f"Jami chiqim: <b>{fmt_amount(s['expense'])}</b>",
            SEP,
        ]
        for c in s["cats"]:
            icon = CAT_ICONS.get(c["slug"], "📌")
            pct = float(c["total"] / s["expense"] * 100) if s["expense"] else 0
            lines.append(f"\n{icon} <b>{c['name']}</b>")
            lines.append(f"   {fmt_amount(c['total'])}  •  {pct:.0f}%  •  {c['count']} ta")
        return "\n".join(lines)

    async def history(self, user_id: int, limit: int = 20) -> str:
        txs = await self.repo.get_recent_for_user(user_id, limit)
        if not txs:
            return f"📋 <b>Tarix</b>\n{SEP}\n\nHali hech narsa yozilmagan."

        lines = [f"📋 <b>Oxirgi {limit} ta yozuv</b>", SEP]
        prev_date = None
        for t in txs:
            if t.transaction_date != prev_date:
                d = t.transaction_date
                lines.append(f"\n<b>{d.day} {MONTHS_UZ[d.month]}</b>")
                prev_date = t.transaction_date
            icon = "💰" if t.type == TransactionType.INCOME else "💸"
            cat_name = t.category.name if t.category else "Boshqa"
            slug = t.category.slug if t.category else "boshqa"
            cat_icon = CAT_ICONS.get(slug, "📌")
            sign = "+" if t.type == TransactionType.INCOME else "–"
            note = f"  · {t.note}" if t.note else ""
            lines.append(
                f"  {icon} {cat_icon} {cat_name}"
                f"   {sign}{fmt_amount(t.amount, t.currency)}"
                f"  <code>#{t.id}</code>{note}"
            )
        return "\n".join(lines)
