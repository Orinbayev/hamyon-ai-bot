"""
Yangi arxitektura entry point.
Ishga tushirish: python main_new.py
"""
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

from app.bot.main import run_bot

if __name__ == "__main__":
    asyncio.run(run_bot())
