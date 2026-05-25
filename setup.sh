#!/bin/bash
set -e

echo "=== Harajat Bot — O'rnatish ==="

# 1. Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Kutubxonalar
pip install --upgrade pip
pip install -r requirements.txt

# 3. .env fayl
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ .env fayl yaratildi — iltimos tahrirlang!"
else
    echo "ℹ️  .env allaqachon mavjud"
fi

# 4. Migration
python manage.py makemigrations
python manage.py migrate

# 5. Standart kategoriyalar
python manage.py loaddata apps/transactions/fixtures/default_categories.json

# 6. Django admin superuser
echo ""
echo "=== Django Admin superuser yaratish ==="
python manage.py createsuperuser

echo ""
echo "✅ O'rnatish tugadi!"
echo ""
echo "Botni ishga tushirish:"
echo "  source .venv/bin/activate"
echo "  python manage.py runbot"
echo ""
echo "Admin panelga kirish:"
echo "  python manage.py runserver"
echo "  http://127.0.0.1:8000/admin/"
