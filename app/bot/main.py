"""
Bot entry point — Dispatcher va Router sozlash.
"""
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.ai.client import GeminiClient
from app.ai.parser import AIParser
from app.bot.handlers import commands, menu, message, start, voice
from app.bot.middlewares.auth import AuthMiddleware
from app.core.config import settings
from app.database.session import create_tables

logger = logging.getLogger("bot")


async def run_bot() -> None:
    await create_tables()

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # AI parser — bir marta yaratiladi, barcha handlerlarga inject qilinadi
    ai_parser = AIParser(GeminiClient())
    dp["ai_parser"] = ai_parser

    # Auth middleware — barcha xabarlarga
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Router tartib muhim: aniq filterlar oldin, umumiy (message) oxirda
    dp.include_router(start.router)
    dp.include_router(commands.router)
    dp.include_router(menu.router)
    dp.include_router(voice.router)
    dp.include_router(message.router)

    logger.info("Bot ishga tushdi...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
