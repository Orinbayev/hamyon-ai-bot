# 💰 Harajat Bot

Shaxsiy moliyaviy Telegram bot. Matn yoki ovozli xabar orqali xarajat va daromadlarni saqlaydi, hisobotlar chiqaradi.

## Stack

- Python 3.11+
- Aiogram 3 (Telegram Bot framework)
- Django 5 + Django Admin
- PostgreSQL / SQLite
- Gemini AI (tahlil + ovoz-matn)

## Tez boshlash

```bash
# 1. Klonlash / papkaga kirish
cd "Harajat Bot"

# 2. Barcha narsani avtomatik o'rnatish
chmod +x setup.sh
./setup.sh
```

Yoki qadamba-qadam:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env faylini tahrirlang (TOKEN, API KEY va DB)

python manage.py makemigrations
python manage.py migrate
python manage.py loaddata apps/transactions/fixtures/default_categories.json
python manage.py createsuperuser
```

## .env sozlamalar

```env
TELEGRAM_BOT_TOKEN=7xxxxxxxxxx:AAxxxxxx   # @BotFather dan
GEMINI_API_KEY=AIzaSyxxxxxx               # Google AI Studio dan
SECRET_KEY=django-insecure-...            # Ixtiyoriy kalit
DEBUG=True

# SQLite (oddiy, fayl asosida):
DB_ENGINE=sqlite

# PostgreSQL (production):
# DB_ENGINE=django.db.backends.postgresql
# DB_NAME=harajat_bot
# DB_USER=postgres
# DB_PASSWORD=secret
# DB_HOST=localhost
# DB_PORT=5432
```

## Ishga tushirish

```bash
# Bot
source .venv/bin/activate
python manage.py runbot

# Admin panel (alohida terminal)
python manage.py runserver
# → http://127.0.0.1:8000/admin/
```

## Bot buyruqlari

| Buyruq | Ta'rif |
|--------|--------|
| `/start` | Botga xush kelibsiz |
| `/help` | Yordam va misollar |
| `/today` | Bugungi hisobot |
| `/week` | Haftalik hisobot |
| `/month` | Oylik hisobot |
| `/balance` | Umumiy balans |
| `/categories` | Kategoriyalar statistikasi |
| `/history` | Oxirgi 20 ta yozuv |
| `/delete` | Oxirgi yozuvni o'chirish |
| `/delete 42` | #42 ID li yozuvni o'chirish |
| `/export` | Excel / CSV eksport |

## Loyiha strukturasi

```
Harajat Bot/
├── config/              # Django sozlamalar
├── apps/
│   ├── users/           # TelegramUser modeli
│   └── transactions/    # Transaction, Category modellari
├── bot/
│   ├── handlers/        # start, message, voice, commands
│   ├── keyboards/       # Inline klaviaturalar
│   ├── middlewares/     # Auth middleware
│   └── main.py          # Bot entry point
├── services/
│   ├── gemini.py        # Gemini AI integratsiya
│   ├── voice.py         # Ovoz yuklash
│   ├── reports.py       # Hisobotlar
│   └── export.py        # Excel/CSV eksport
└── manage.py
```

## Kelajakda qo'shish mumkin

- [ ] Grafik diagrammalar (matplotlib / plotly)
- [ ] Oylik avtomatik hisobot (APScheduler)
- [ ] Byudjet belgilash va ogohlantirishlar
- [ ] Valyuta kursi (so'm/dollar konvertatsiya)
- [ ] Ko'p foydalanuvchi + oilaviy hisoblar
