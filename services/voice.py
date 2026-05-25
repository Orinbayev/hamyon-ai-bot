"""
Voice service — Telegram voice xabarlarini yuklab olish.
"""

import logging

from aiogram import Bot
from aiogram.types import Voice

logger = logging.getLogger("services")


async def download_voice(bot: Bot, voice: Voice) -> tuple[bytes, str]:
    """
    Telegram ovozli xabarni bytes sifatida yuklab oladi.
    Returns: (audio_bytes, mime_type)
    """
    file = await bot.get_file(voice.file_id)
    file_bytes = await bot.download_file(file.file_path)
    audio_bytes = file_bytes.read()

    mime_type = voice.mime_type or "audio/ogg"
    logger.debug("Voice yuklandi: %d bytes, mime: %s", len(audio_bytes), mime_type)
    return audio_bytes, mime_type
