"""
Bot entry point — Aiogram dispatcher va router sozlash.
"""

import asyncio
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

from bot.handlers import admin, commands, edit, menu, message, start, subscription, voice
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.subscription import SubscriptionMiddleware
from bot.tasks.notifications import run_notification_loop

logger = logging.getLogger("bot")


async def main():
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware — tartibi muhim: Auth → Subscription
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())

    # Routerlar tartibi muhim:
    # 1. admin   — /admin va adm:* callbacks (oldin, cheklov bilan)
    # 2. start   — /start, /help
    # 3. commands — /today, /week va boshqa buyruqlar
    # 4. menu   — reply keyboard tugmalari (aniq matnlar)
    # 5. voice  — ovozli xabarlar
    # 6. message — matnli xabarlar (AI tahlil, eng oxirgi)
    dp.include_router(admin.router)
    dp.include_router(subscription.router)
    dp.include_router(start.router)
    dp.include_router(commands.router)
    dp.include_router(menu.router)
    dp.include_router(edit.router)
    dp.include_router(voice.router)
    dp.include_router(message.router)

    # Render deploy paytida eski bot sessiyasini yopish (TelegramConflictError oldini olish)
    await bot.delete_webhook(drop_pending_updates=True)

    asyncio.create_task(run_notification_loop(bot))

    logger.info("Bot polling boshlandi...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
