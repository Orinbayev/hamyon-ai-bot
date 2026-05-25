from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

MENU_BUTTONS = {
    "📅 Bugun", "📆 Hafta", "🗓 Oy",
    "💰 Balans", "📊 Kategoriyalar",
    "📋 Tarix", "📤 Eksport",
    "🗑 Tozalash",
}


def main_menu() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📅 Bugun"),
        KeyboardButton(text="📆 Hafta"),
        KeyboardButton(text="🗓 Oy"),
    )
    builder.row(
        KeyboardButton(text="💰 Balans"),
        KeyboardButton(text="📊 Kategoriyalar"),
    )
    builder.row(
        KeyboardButton(text="📋 Tarix"),
        KeyboardButton(text="📤 Eksport"),
    )
    builder.row(
        KeyboardButton(text="🗑 Tozalash"),
    )
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Xarajat yoki kirimni yozing...",
    )
