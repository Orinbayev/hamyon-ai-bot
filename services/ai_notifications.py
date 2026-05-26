"""
AI yordamida avtomatik bildirishnomalar yaratish.
Faolsizlik eslatmasi — shablonlar orqali.
Haftalik/oylik tahlil — Gemini orqali.
"""

import logging
import random
from decimal import Decimal

from google.genai import types

from services.gemini import _call

logger = logging.getLogger("services")


def _fmt(amount) -> str:
    return f"{float(amount):,.0f}".replace(",", " ") + " so'm"


_INACTIVE_TEMPLATES = [
    "👋 Salom, {name}!\n\n"
    "📅 {days} kundan beri xarajat yoki kirim yozmadingiz.\n\n"
    "💡 Pul oqimini kuzatish — moliyaviy erkinlikka birinchi qadam!\n\n"
    "Bugun nima xarajat qildingiz? ✍️",

    "🔔 {name}, hamyoningizni eslatib o'tamiz!\n\n"
    "{days} kun o'tdi so'nggi yozuvdan.\n"
    "📊 So'nggi ko'rsatkich: {last_date}\n\n"
    "Kichik yozuv ham katta nazoratga olib keladi 💪",

    "💸 {name}, {days} kunlik tanaffus — bu ko'p!\n\n"
    "Xarajatlarni yozmasangiz, pul qayerga ketganini bilolmaysiz 😅\n\n"
    "Bir daqiqa ajrating va bugungi tranzaksiyani qo'shing 🎯",
]


def inactive_reminder(name: str, days: int, last_date: str) -> str:
    template = random.choice(_INACTIVE_TEMPLATES)
    return template.format(name=name, days=days, last_date=last_date)


_WEEKLY_PROMPT = """\
Foydalanuvchiga qisqa haftalik moliyaviy tahlil xabarini O'zbek tilida yoz.

Foydalanuvchi ismi: {name}

Bu hafta:
- Kirim: {this_income}
- Chiqim: {this_expense}
- Balans: {this_balance}
- Yozuvlar: {this_count} ta

O'tgan hafta:
- Kirim: {prev_income}
- Chiqim: {prev_expense}

Eng ko'p xarajat kategoriyasi: {top_cat}

Ko'rsatmalar:
- 3-4 qisqa gap yoz
- O'zgarishlarni foizda ko'rsat (o'tgan haftaga nisbatan)
- Motivatsion va amaliy maslahat ber
- Emoji ishlat
- FAQAT xabarni yoz, boshqa hech narsa yo'q\
"""

_MONTHLY_PROMPT = """\
Foydalanuvchiga oylik moliyaviy tahlil xabarini O'zbek tilida yoz.

Foydalanuvchi ismi: {name}

Bu oy:
- Kirim: {this_income}
- Chiqim: {this_expense}
- Balans: {this_balance}
- Yozuvlar: {this_count} ta

O'tgan oy:
- Kirim: {prev_income}
- Chiqim: {prev_expense}

Top xarajat kategoriyalari:
{top_cats}

Ko'rsatmalar:
- 4-5 gap, chuqur tahlil va taqqoslash
- Foizda o'zgarishlarni ko'rsat
- Yaxshilash uchun aniq maslahat ber
- Emoji ishlat
- FAQAT xabarni yoz\
"""


async def generate_weekly_insight(
    name: str,
    this_week: dict,
    prev_week: dict,
) -> str:
    top_cats = this_week.get("top_cats", [])
    top_cat = top_cats[0].get("category__name") or "Boshqa" if top_cats else "—"

    prompt = _WEEKLY_PROMPT.format(
        name=name,
        this_income=_fmt(this_week.get("income", 0)),
        this_expense=_fmt(this_week.get("expense", 0)),
        this_balance=_fmt(this_week.get("balance", 0)),
        this_count=this_week.get("count", 0),
        prev_income=_fmt(prev_week.get("income", 0)),
        prev_expense=_fmt(prev_week.get("expense", 0)),
        top_cat=top_cat,
    )
    config = types.GenerateContentConfig(temperature=0.7)
    try:
        text = await _call(prompt, config)
        header = "📊 <b>Haftalik hisobot</b>\n\n"
        return header + text.strip()
    except Exception as e:
        logger.warning("Weekly insight Gemini xatosi: %s", e)
        return (
            f"📊 <b>Haftalik hisobot</b>\n\n"
            f"💰 Kirim: {_fmt(this_week.get('income', 0))}\n"
            f"💸 Chiqim: {_fmt(this_week.get('expense', 0))}\n"
            f"📈 Balans: {_fmt(this_week.get('balance', 0))}\n"
            f"📝 Yozuvlar: {this_week.get('count', 0)} ta"
        )


async def generate_monthly_insight(
    name: str,
    this_month: dict,
    prev_month: dict,
) -> str:
    cats = this_month.get("top_cats", [])
    top_cats_text = "\n".join(
        f"  - {c.get('category__name') or 'Boshqa'}: {_fmt(c['total'])}"
        for c in cats
    ) or "  — (ma'lumot yo'q)"

    prompt = _MONTHLY_PROMPT.format(
        name=name,
        this_income=_fmt(this_month.get("income", 0)),
        this_expense=_fmt(this_month.get("expense", 0)),
        this_balance=_fmt(this_month.get("balance", 0)),
        this_count=this_month.get("count", 0),
        prev_income=_fmt(prev_month.get("income", 0)),
        prev_expense=_fmt(prev_month.get("expense", 0)),
        top_cats=top_cats_text,
    )
    config = types.GenerateContentConfig(temperature=0.7)
    try:
        text = await _call(prompt, config)
        header = "🗓 <b>Oylik hisobot</b>\n\n"
        return header + text.strip()
    except Exception as e:
        logger.warning("Monthly insight Gemini xatosi: %s", e)
        return (
            f"🗓 <b>Oylik hisobot</b>\n\n"
            f"💰 Kirim: {_fmt(this_month.get('income', 0))}\n"
            f"💸 Chiqim: {_fmt(this_month.get('expense', 0))}\n"
            f"📈 Balans: {_fmt(this_month.get('balance', 0))}\n"
            f"📝 Yozuvlar: {this_month.get('count', 0)} ta"
        )
