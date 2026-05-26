"""
Avtomatik bildirishnomalar background task-i.
Har soatda ishga tushadi, O'zbekiston vaqti (UTC+5) bo'yicha:
  - 9-20: faolsiz foydalanuvchilarga eslatma (max 3 kunda bir)
  - Dushanba 9:00: haftalik Gemini tahlil
  - Har oyning 1-si 10:00: oylik Gemini tahlil
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta, date

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from asgiref.sync import sync_to_async
from django.utils import timezone as dj_tz

from services import ai_notifications
from services.reports import get_period_stats

logger = logging.getLogger("bot")

UZB_TZ = timezone(timedelta(hours=5))
INACTIVITY_DAYS = 2
REMIND_COOLDOWN_DAYS = 3
MAX_BATCH = 30  # bitta sikl uchun maksimal foydalanuvchi soni


@sync_to_async
def _get_inactive_users():
    from apps.users.models import TelegramUser
    from apps.transactions.models import Transaction
    from django.db.models import Max

    cutoff = datetime.now(UZB_TZ).date() - timedelta(days=INACTIVITY_DAYS)
    remind_cutoff = datetime.now(UZB_TZ) - timedelta(days=REMIND_COOLDOWN_DAYS)

    users = TelegramUser.objects.filter(is_active=True).annotate(
        last_tx=Max("transactions__created_at")
    )

    result = []
    for u in users[:MAX_BATCH]:
        last_tx = u.last_tx
        if last_tx is None:
            continue
        last_tx_date = last_tx.astimezone(UZB_TZ).date()
        if last_tx_date > cutoff:
            continue
        if u.last_reminded_at and u.last_reminded_at > remind_cutoff:
            continue
        result.append((u, last_tx_date, (datetime.now(UZB_TZ).date() - last_tx_date).days))
    return result


@sync_to_async
def _get_active_users_for_weekly():
    from apps.users.models import TelegramUser
    from django.db.models import Count

    remind_cutoff = datetime.now(UZB_TZ) - timedelta(days=6)
    return list(
        TelegramUser.objects.filter(is_active=True)
        .annotate(tx_count=Count("transactions"))
        .filter(tx_count__gt=0)
        .exclude(last_reminded_at__gt=remind_cutoff)[:MAX_BATCH]
    )


@sync_to_async
def _get_active_users_for_monthly():
    from apps.users.models import TelegramUser
    from django.db.models import Count

    remind_cutoff = datetime.now(UZB_TZ) - timedelta(days=27)
    return list(
        TelegramUser.objects.filter(is_active=True)
        .annotate(tx_count=Count("transactions"))
        .filter(tx_count__gt=0)
        .exclude(last_reminded_at__gt=remind_cutoff)[:MAX_BATCH]
    )


@sync_to_async
def _mark_reminded(user_id: int) -> None:
    from apps.users.models import TelegramUser
    TelegramUser.objects.filter(id=user_id).update(last_reminded_at=datetime.now(UZB_TZ))


async def _safe_send(bot: Bot, chat_id: int, text: str) -> bool:
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML")
        return True
    except TelegramForbiddenError:
        logger.debug("User %s boti blokladi, o'tkazildi.", chat_id)
        return False
    except TelegramBadRequest as e:
        logger.warning("send_message xatosi %s: %s", chat_id, e)
        return False
    except Exception as e:
        logger.exception("Kutilmagan xato %s: %s", chat_id, e)
        return False


async def _send_inactivity_reminders(bot: Bot) -> None:
    users_data = await _get_inactive_users()
    if not users_data:
        return

    sent = 0
    for user, last_date, days in users_data:
        name = (user.full_name or "").split()[0] or "Salom"
        last_date_str = last_date.strftime("%d.%m.%Y")
        text = ai_notifications.inactive_reminder(name, days, last_date_str)
        if await _safe_send(bot, user.telegram_id, text):
            await _mark_reminded(user.id)
            sent += 1
        await asyncio.sleep(0.05)  # Telegram rate limit

    if sent:
        logger.info("Faolsizlik eslatmasi yuborildi: %d ta foydalanuvchi", sent)


async def _send_weekly_insights(bot: Bot) -> None:
    users = await _get_active_users_for_weekly()
    if not users:
        return

    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    prev_monday = this_monday - timedelta(days=7)
    prev_sunday = this_monday - timedelta(days=1)

    sent = 0
    for user in users:
        try:
            this_week = await get_period_stats(user, this_monday, today)
            prev_week = await get_period_stats(user, prev_monday, prev_sunday)

            if this_week["count"] == 0 and prev_week["count"] == 0:
                continue

            name = (user.full_name or "").split()[0] or "Salom"
            text = await ai_notifications.generate_weekly_insight(name, this_week, prev_week)

            if await _safe_send(bot, user.telegram_id, text):
                await _mark_reminded(user.id)
                sent += 1
            await asyncio.sleep(1)  # Gemini + Telegram rate limit
        except Exception as e:
            logger.warning("Haftalik insight xatosi user %s: %s", user.telegram_id, e)

    if sent:
        logger.info("Haftalik insight yuborildi: %d ta foydalanuvchi", sent)


async def _send_monthly_insights(bot: Bot) -> None:
    users = await _get_active_users_for_monthly()
    if not users:
        return

    today = date.today()
    this_month_start = today.replace(day=1)
    if today.month == 1:
        prev_month_start = today.replace(year=today.year - 1, month=12, day=1)
        prev_month_end = today.replace(day=1) - timedelta(days=1)
    else:
        prev_month_start = today.replace(month=today.month - 1, day=1)
        prev_month_end = today.replace(day=1) - timedelta(days=1)

    sent = 0
    for user in users:
        try:
            this_month = await get_period_stats(user, this_month_start, today)
            prev_month = await get_period_stats(user, prev_month_start, prev_month_end)

            if this_month["count"] == 0 and prev_month["count"] == 0:
                continue

            name = (user.full_name or "").split()[0] or "Salom"
            text = await ai_notifications.generate_monthly_insight(name, this_month, prev_month)

            if await _safe_send(bot, user.telegram_id, text):
                await _mark_reminded(user.id)
                sent += 1
            await asyncio.sleep(1)
        except Exception as e:
            logger.warning("Oylik insight xatosi user %s: %s", user.telegram_id, e)

    if sent:
        logger.info("Oylik insight yuborildi: %d ta foydalanuvchi", sent)


async def run_notification_loop(bot: Bot) -> None:
    """Bot ishga tushgandan 2 daqiqa keyin boshlanadi, har soatda ishlaydi."""
    await asyncio.sleep(120)
    while True:
        try:
            now = datetime.now(UZB_TZ)
            hour = now.hour
            weekday = now.weekday()   # 0 = Dushanba
            month_day = now.day

            if not (8 <= hour <= 21):
                await asyncio.sleep(3600)
                continue

            # Oylik: 1-sana, soat 10
            if month_day == 1 and hour == 10:
                await _send_monthly_insights(bot)

            # Haftalik: Dushanba, soat 9
            elif weekday == 0 and hour == 9:
                await _send_weekly_insights(bot)

            # Faolsizlik: soat 9-20, har soatda
            elif 9 <= hour <= 20:
                await _send_inactivity_reminders(bot)

        except Exception as e:
            logger.exception("Notification loop xatosi: %s", e)

        await asyncio.sleep(3600)
