"""
Premium format helpers — barcha xabarlarda ishlatiladi.
"""
from datetime import date
from decimal import Decimal

SEP = "━" * 15

CAT_ICONS: dict[str, str] = {
    "ovqat": "🍽", "taxi": "🚕", "transport": "🚌",
    "kiyim": "👗", "internet": "🌐", "telefon": "📱",
    "uy": "🏠", "kommunal": "💡", "oqish": "📚",
    "salomatlik": "💊", "kongilochar": "🎭", "ish_haqi": "💼",
    "qarz": "🤝", "sovga": "🎁", "boshqa": "📌",
}

CAT_NAMES: dict[str, str] = {
    "ovqat": "Ovqat", "taxi": "Taxi", "transport": "Transport",
    "kiyim": "Kiyim", "internet": "Internet", "telefon": "Telefon",
    "uy": "Uy", "kommunal": "Kommunal", "oqish": "O'qish",
    "salomatlik": "Salomatlik", "kongilochar": "Ko'ngilochar",
    "ish_haqi": "Ish haqi", "qarz": "Qarz", "sovga": "Sovg'a",
    "boshqa": "Boshqa",
}

PAYMENT_LABELS: dict[str, str] = {
    "cash": "Naqd pul", "card": "Karta",
    "click": "Click", "payme": "Payme",
    "bank": "Bank o'tkazma", "other": "Boshqa",
}

MONTHS_UZ: dict[int, str] = {
    1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
    5: "May", 6: "Iyun", 7: "Iyul", 8: "Avgust",
    9: "Sentabr", 10: "Oktabr", 11: "Noyabr", 12: "Dekabr",
}

DAYS_UZ: dict[int, str] = {
    0: "Dushanba", 1: "Seshanba", 2: "Chorshanba",
    3: "Payshanba", 4: "Juma", 5: "Shanba", 6: "Yakshanba",
}

NUM_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]


def fmt_amount(amount, currency: str = "UZS") -> str:
    """45 000 so'm  /  $ 100  /  1 500 ₽"""
    formatted = f"{float(amount):,.0f}".replace(",", " ")
    if currency == "USD":
        return f"$ {formatted}"
    if currency == "RUB":
        return f"{formatted} ₽"
    return f"{formatted} so'm"


def fmt_signed(balance) -> str:
    """+2 500 000 so'm  yoki  –245 000 so'm"""
    bal = Decimal(str(balance))
    if bal >= 0:
        return f"+{fmt_amount(bal)}"
    return f"–{fmt_amount(abs(bal))}"


def fmt_date(date_str: str | None) -> str:
    if not date_str or date_str == date.today().isoformat():
        return "Bugun"
    try:
        return date.fromisoformat(date_str).strftime("%d.%m.%Y")
    except ValueError:
        return date_str or "Bugun"
