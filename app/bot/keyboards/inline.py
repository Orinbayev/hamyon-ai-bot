from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def confirm_transactions_keyboard(count: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"✅ Saqlash ({count} ta)", callback_data="confirm_save"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="cancel_save"),
    )
    return builder.as_markup()


def delete_confirm_keyboard(tx_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Ha, o'chirish", callback_data=f"delete_confirm:{tx_id}"),
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
    builder.row(InlineKeyboardButton(text="❌ Bekor", callback_data="export:cancel"))
    return builder.as_markup()


def export_period_keyboard(fmt: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Bugun", callback_data=f"export_period:{fmt}:today"),
        InlineKeyboardButton(text="📆 Bu hafta", callback_data=f"export_period:{fmt}:week"),
    )
    builder.row(
        InlineKeyboardButton(text="🗓 Bu oy", callback_data=f"export_period:{fmt}:month"),
        InlineKeyboardButton(text="📋 Hammasi", callback_data=f"export_period:{fmt}:all"),
    )
    return builder.as_markup()
