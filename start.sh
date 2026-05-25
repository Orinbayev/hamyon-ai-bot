#!/usr/bin/env bash
set -e

echo "=== HamyonAI ishga tushmoqda ==="

# Telegram bot orqa fonda
python manage.py runbot &
BOT_PID=$!
echo "Bot ishga tushdi (PID: $BOT_PID)"

# Django web server oldingi rejimda (container shu bilan tirik turadi)
echo "Web server ishga tushmoqda..."
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 2 \
  --timeout 120 \
  --access-logfile -
