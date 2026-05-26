import logging
from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.users.models import TelegramUser
from bot.keyboards.reply import main_menu

logger = logging.getLogger("bot")
router = Router(name="start")

SEP = "━" * 15


@router.message(Command("start"))
async def cmd_start(message: Message, db_user: TelegramUser):
    today = date.today().strftime("%d.%m.%Y")
    name = db_user.full_name.split()[0]
    text = (
        f"Salom, <b>{name}</b>! 👋\n"
        f"Bugun {today}\n\n"
        f"<b>Harajat Bot</b> — shaxsiy moliyaviy daftaringiz.\n\n"
        f"Xarajat yoki kirimni oddiy gapda yozing:\n\n"
        f"  <i>Ovqatga 45 ming</i>\n"
        f"  <i>Taxi 20 000</i>\n"
        f"  <i>Maosh 3 million kirim</i>\n\n"
        f"Yoki 🎤 ovozli xabar yuboring."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        f"<b>Qanday ishlatish</b>\n\n"
        f"Shunchaki matn yoki 🎤 ovoz yuboring:\n\n"
        f"  <i>Ovqatga 45 ming ketdi</i>\n"
        f"  <i>Taxi 20 000</i>\n"
        f"  <i>Maosh 5 million tushdi</i>\n"
        f"  <i>Bugun ovqat 40 ming, taxi 15 ming</i>\n\n"
        f"{SEP}\n"
        f"📊 <b>Tugmalar</b>\n\n"
        f"📅 Bugun — bugungi hisobot\n"
        f"📆 Hafta — haftalik hisobot\n"
        f"🗓 Oy — oylik hisobot\n"
        f"💰 Balans — umumiy holat\n"
        f"📊 Kategoriyalar — xarajat taqsimoti\n"
        f"📋 Tarix — oxirgi yozuvlar\n"
        f"📤 Eksport — Excel / CSV fayl\n\n"
        f"{SEP}\n"
        f"✏️ <b>Boshqarish</b>\n\n"
        f"/delete — oxirgi yozuvni o'chirish\n"
        f"/delete 42 — #42 raqamli yozuvni o'chirish\n"
        f"/undo — eng oxirgi kiritilgan yozuvni bekor qilish\n"
        f"/clear — barcha tarixni tozalash\n\n"
        f"{SEP}\n"
        f"💡 <b>Maslahatlar</b>\n\n"
        f"Izoh qo'shish: <code>50k taxi // ish uchun</code>\n"
        f"Yozuv saqlanganidan keyin <b>✏️ Kategoriya</b> tugmasi chiqadi\n"
        f"— noto'g'ri kategoriyani o'sha yerda o'zgartiring."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu())
