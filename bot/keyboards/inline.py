"""
Inline klaviaturalar.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

CATEGORY_LIST = [
    ("ovqat",       "🍽 Ovqat"),
    ("taxi",        "🚕 Taxi"),
    ("transport",   "🚌 Transport"),
    ("kiyim",       "👗 Kiyim"),
    ("internet",    "🌐 Internet"),
    ("telefon",     "📱 Telefon"),
    ("uy",          "🏠 Uy"),
    ("kommunal",    "💡 Kommunal"),
    ("oqish",       "📚 O'qish"),
    ("salomatlik",  "💊 Salomatlik"),
    ("kongilochar", "🎭 Ko'ngilochar"),
    ("ish_haqi",    "💼 Ish haqi"),
    ("qarz",        "🤝 Qarz"),
    ("sovga",       "🎁 Sovg'a"),
    ("boshqa",      "📌 Boshqa"),
]

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


def _fmt_short(amount, currency="UZS") -> str:
    n = float(amount)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}mln"
    if n >= 1000:
        return f"{n / 1000:.0f}k"
    return str(int(n))


def voice_retry_keyboard(file_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Qayta urinish", callback_data=f"voice:retry:{file_id}"))
    return builder.as_markup()


def confirm_transactions_keyboard(count: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"✅ Saqlash ({count} ta)", callback_data="confirm_save"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_save"),
    )
    return builder.as_markup()


def delete_confirm_keyboard(transaction_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Ha, o'chirish", callback_data=f"delete_confirm:{transaction_id}"),
        InlineKeyboardButton(text="↩️ Yo'q", callback_data="delete_cancel"),
    )
    return builder.as_markup()


def clear_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Excel yuklab, so'ng tozalash", callback_data="clear_export"))
    builder.row(
        InlineKeyboardButton(text="🗑 Shunday tozalash", callback_data="clear_confirm"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="clear_cancel"),
    )
    return builder.as_markup()


def clear_after_export_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Ha, tozalash", callback_data="clear_confirm"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="clear_cancel"),
    )
    return builder.as_markup()


def export_format_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Excel (.xlsx)", callback_data="export:excel"),
        InlineKeyboardButton(text="📄 CSV (.csv)", callback_data="export:csv"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor", callback_data="export:cancel"),
    )
    return builder.as_markup()


def export_period_keyboard(fmt: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Bugun", callback_data=f"export_period:{fmt}:today"),
        InlineKeyboardButton(text="📅 Bu hafta", callback_data=f"export_period:{fmt}:week"),
    )
    builder.row(
        InlineKeyboardButton(text="📅 Bu oy", callback_data=f"export_period:{fmt}:month"),
        InlineKeyboardButton(text="📅 Hammasi", callback_data=f"export_period:{fmt}:all"),
    )
    return builder.as_markup()


def history_delete_keyboard(txs: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    row: list[InlineKeyboardButton] = []
    for i, tx in enumerate(txs):
        row.append(InlineKeyboardButton(
            text=f"🗑 #{tx.id}",
            callback_data=f"tx:del:{tx.id}",
        ))
        if len(row) == 5 or i == len(txs) - 1:
            builder.row(*row)
            row = []
    return builder.as_markup()


def tx_delete_confirm_keyboard(tx_id: int, back_page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Ha, o'chirish", callback_data=f"tx:del_ok:{tx_id}:{back_page}"),
        InlineKeyboardButton(text="↩️ Bekor", callback_data=f"tx:view:{tx_id}:{back_page}"),
    )
    return builder.as_markup()


def tx_quick_actions_keyboard(tx_id: int) -> InlineKeyboardMarkup:
    """Tranzaksiya saqlanganidan keyin tezkor amallar."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Kategoriya", callback_data=f"tx:cat_change:{tx_id}:0"),
        InlineKeyboardButton(text="↩️ Bekor qilish", callback_data=f"tx:undo:{tx_id}"),
    )
    return builder.as_markup()


def category_select_keyboard(tx_id: int, back_page: int = 0) -> InlineKeyboardMarkup:
    """Kategoriya tanlash klaviaturasi."""
    builder = InlineKeyboardBuilder()
    for slug, label in CATEGORY_LIST:
        builder.button(text=label, callback_data=f"tx:cat_set:{tx_id}:{slug}:{back_page}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(
        text="❌ Bekor",
        callback_data=f"tx:view:{tx_id}:{back_page}",
    ))
    return builder.as_markup()


def tx_detail_keyboard(tx_id: int, back_page: int = 0) -> InlineKeyboardMarkup:
    """Tranzaksiya detalida to'liq tahrirlash tugmalari."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Kategoriya", callback_data=f"tx:cat_change:{tx_id}:{back_page}"),
        InlineKeyboardButton(text="💰 Miqdor",     callback_data=f"tx:edit_amount:{tx_id}:{back_page}"),
    )
    builder.row(
        InlineKeyboardButton(text="📅 Sana",       callback_data=f"tx:edit_date:{tx_id}:{back_page}"),
        InlineKeyboardButton(text="📝 Izoh",       callback_data=f"tx:edit_note:{tx_id}:{back_page}"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑 O'chirish",  callback_data=f"tx:del:{tx_id}"),
        InlineKeyboardButton(text="↩️ Tarix",      callback_data=f"hist:page:{back_page}"),
    )
    return builder.as_markup()


def history_full_keyboard(txs: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """
    Har bir tranzaksiya — bosiladigan tugma.
    Sana ajratgichlari (bosilmaydi) + navigatsiya.
    """
    builder = InlineKeyboardBuilder()
    prev_date = None

    for tx in txs:
        # Sana ajratgich (bosilmaydi)
        if tx.transaction_date != prev_date:
            d = tx.transaction_date
            builder.row(InlineKeyboardButton(
                text=f"── {d.day} {MONTHS_UZ[d.month]} ──",
                callback_data="hist:noop",
            ))
            prev_date = tx.transaction_date

        # Tranzaksiya tugmasi
        t_icon = "💰" if tx.type == "income" else "💸"
        slug = tx.category.slug if tx.category else "boshqa"
        cat_icon = CAT_ICONS.get(slug, "📌")
        cat_name = (tx.category.name[:12] if tx.category else "Boshqa")
        amt = _fmt_short(tx.amount, tx.currency)
        cur = "so'm" if tx.currency == "UZS" else ("$" if tx.currency == "USD" else "₽")
        note_hint = "  ·" if tx.note else ""
        btn_text = f"{t_icon}{cat_icon} {cat_name}  {amt} {cur}{note_hint}"

        builder.row(InlineKeyboardButton(
            text=btn_text,
            callback_data=f"tx:view:{tx.id}:{page}",
        ))

    # Navigatsiya
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"hist:page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="hist:noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"hist:page:{page + 1}"))
    builder.row(*nav)

    return builder.as_markup()


def history_nav_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Oddiy navigatsiya (tarix tekst ko'rinishi uchun)."""
    builder = InlineKeyboardBuilder()
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"hist:page:{page - 1}"))
    buttons.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="hist:noop"))
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"hist:page:{page + 1}"))
    builder.row(*buttons)
    return builder.as_markup()
