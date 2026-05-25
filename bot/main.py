"""
Bot entry point — Aiogram dispatcher va router sozlash.
"""

import logging
import os

import django

# Django ni ishga tushirish (runbot.py management command orqali ham bo'ladi,
# lekin to'g'ridan-to'g'ri python bot/main.py bilan ishga tushirilganda ham ishlaydi)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from django.conf import settings

from bot.handlers import admin, commands, menu, message, start, voice
from bot.middlewares.auth import AuthMiddleware

logger = logging.getLogger("bot")


async def main():
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware — message va callback_query uchun
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Routerlar tartibi muhim:
    # 1. admin   — /admin va adm:* callbacks (oldin, cheklov bilan)
    # 2. start   — /start, /help
    # 3. commands — /today, /week va boshqa buyruqlar
    # 4. menu   — reply keyboard tugmalari (aniq matnlar)
    # 5. voice  — ovozli xabarlar
    # 6. message — matnli xabarlar (AI tahlil, eng oxirgi)
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(commands.router)
    dp.include_router(menu.router)
    dp.include_router(voice.router)
    dp.include_router(message.router)

    logger.info("Bot polling boshlandi...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
