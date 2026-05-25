import asyncio
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger("bot")


class Command(BaseCommand):
    help = "Telegram botni ishga tushiradi"

    def handle(self, *args, **options):
        from bot.main import main

        self.stdout.write(self.style.SUCCESS("Bot ishga tushmoqda..."))
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Bot to'xtatildi."))
