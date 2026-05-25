"""
Gemini AI service — google-genai SDK, to'liq async, model fallback bilan.
"""

import json
import logging
from datetime import date, timedelta

from google import genai
from google.genai import types
from django.conf import settings

from services.token_tracker import tracker

logger = logging.getLogger("services")

client = genai.Client(api_key=settings.GEMINI_API_KEY)

MODEL = settings.GEMINI_MODEL

# 429/404 xatolarda navbat bilan urinib ko'riladigan modellar
# (client.models.list() bilan tekshirilgan haqiqiy nomlar)
FALLBACK_MODELS = [
    "gemini-2.5-flash",       # 5 RPM, 20 RPD
    "gemini-3.1-flash-lite",  # 15 RPM, 500 RPD — eng ko'p quota
    "gemini-3-flash-preview", # 5 RPM, 20 RPD
    "gemini-2.0-flash-lite",  # backup
    "gemini-flash-latest",    # alias
]

SYSTEM_PROMPT = """
Sen moliyaviy yordamchi botsan. Foydalanuvchi o'zbek tilida moliyaviy xabarlar yozadi.
Sening vazifang — xabardagi BARCHA moliyaviy tranzaksiyalarni ajratib, JSON formatida qaytarish.

QOIDALAR:
1. type: "income" (kirim, tushdi, oldi, berdi menga, topdi) yoki "expense" (chiqim, sarfladi, ketdi, to'ladi)
2. amount: faqat son (vergul, bo'sh joy yo'q)
   - "ming" = 1000, "million" yoki "mln" = 1000000
   - "45 ming" → 45000, "2 million" → 2000000, "1.5 ming" → 1500
3. currency: "UZS" (so'm, sum, ming, million), "USD" (dollar, $), "RUB" (rubl). Default: "UZS"
4. category (sluglar):
   - ovqat: ovqat, restoran, kafe, tushlik, nonushta, grocery
   - taxi: taxi, taksi, yandex taxi, uber
   - transport: avtobus, metro, marshrutka
   - kiyim: kiyim, poyabzal, aksessuar
   - internet: internet, wi-fi
   - telefon: telefon to'lovi, uyali aloqa
   - uy: uy ijarasi, kvartira
   - kommunal: gaz, suv, elektr, kommunal
   - oqish: o'qish, kurs, ta'lim, kitob
   - salomatlik: dorixona, shifoxona, dori
   - kongilochar: kino, o'yin, dam olish
   - ish_haqi: maosh, oylik, ish haqi
   - qarz: qarz, kredit, qarz berdi, qarz oldi
   - sovga: sovg'a, present
   - boshqa: boshqa barcha narsa
5. payment_method: "cash" (naqd), "card" (karta), "click", "payme", "bank", "other"
6. date: "today" (bugun), "yesterday" (kecha), yoki "YYYY-MM-DD". Default: "today"
7. note: qisqa izoh o'zbek tilida

MUHIM:
- Bitta xabarda bir nechta tranzaksiya bo'lishi mumkin — BARCHASINI ajrat
- "Anvar menga 500 ming berdi" → income, category: "qarz"
- "Kartadan 300 ming chiqim bo'ldi" → expense, payment_method: "card"

Javob formati — FAQAT sof JSON array, boshqa hech narsa yozma:
[{"type":"expense","amount":45000,"currency":"UZS","category":"ovqat","payment_method":"cash","date":"today","note":"ovqat"}]

Agar tranzaksiya topilmasa: []
"""


def _clean_json(text: str) -> str:
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return text.strip()


def _resolve_date(date_str: str) -> str:
    today = date.today()
    if date_str in ("today", "bugun", "hozir", ""):
        return today.isoformat()
    if date_str in ("yesterday", "kecha", "kechagi"):
        return (today - timedelta(days=1)).isoformat()
    return date_str


def _validate(item: dict) -> dict | None:
    try:
        t_type = item.get("type", "").lower()
        if t_type not in ("income", "expense"):
            return None
        amount = float(str(item.get("amount", 0)).replace(",", "").replace(" ", ""))
        if amount <= 0:
            return None
        return {
            "type": t_type,
            "amount": amount,
            "currency": item.get("currency", "UZS").upper(),
            "category": item.get("category", "boshqa").lower(),
            "payment_method": item.get("payment_method", "cash").lower(),
            "date": _resolve_date(item.get("date", "today")),
            "note": item.get("note", ""),
        }
    except (ValueError, TypeError) as e:
        logger.warning("Noto'g'ri tranzaksiya: %s — %s", item, e)
        return None


def _parse_items(raw_text: str) -> list[dict]:
    items = json.loads(_clean_json(raw_text))
    if not isinstance(items, list):
        return []
    return [v for item in items if (v := _validate(item))]


def _is_quota_error(err: Exception) -> bool:
    msg = str(err)
    return any(code in msg for code in ("429", "404", "RESOURCE_EXHAUSTED", "NOT_FOUND"))


async def _call(contents, config: types.GenerateContentConfig) -> str:
    """Asosiy modeldan boshlaydi, xato bo'lsa fallback modellarni urinadi."""
    models_to_try = [MODEL] + [m for m in FALLBACK_MODELS if m != MODEL]
    last_err: Exception | None = None

    for model_name in models_to_try:
        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            if model_name != MODEL:
                logger.info("Fallback model ishlatildi: %s", model_name)
            meta = getattr(response, "usage_metadata", None)
            if meta:
                tracker.record(
                    prompt_tokens=getattr(meta, "prompt_token_count", 0) or 0,
                    response_tokens=getattr(meta, "candidates_token_count", 0) or 0,
                    total_tokens=getattr(meta, "total_token_count", 0) or 0,
                    model=model_name,
                )
            return response.text
        except Exception as e:
            if _is_quota_error(e):
                logger.warning("Model %s ishlamadi, keyingisini urinmoqda...", model_name)
                last_err = e
            else:
                raise

    raise last_err or RuntimeError("Barcha Gemini modellari ishlamadi")


async def parse_text(text: str) -> list[dict]:
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.1,
    )
    try:
        raw = await _call(text, config)
        return _parse_items(raw)
    except json.JSONDecodeError as e:
        logger.error("JSON parse xatosi: %s", e)
        return []
    except Exception as e:
        logger.exception("Gemini text xatosi: %s", e)
        raise


async def parse_voice(audio_bytes: bytes, mime_type: str = "audio/ogg") -> list[dict]:
    prompt = (
        "Quyidagi ovozli xabarda moliyaviy tranzaksiyalar bor. "
        "Avval o'zbek tiliga transkripsiya qil, keyin tranzaksiyalarni JSON formatida qaytarr."
    )
    contents = [
        types.Part(inline_data=types.Blob(data=audio_bytes, mime_type=mime_type)),
        prompt,
    ]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.1,
    )
    try:
        raw = await _call(contents, config)
        return _parse_items(raw)
    except json.JSONDecodeError as e:
        logger.error("Voice JSON parse xatosi: %s", e)
        return []
    except Exception as e:
        logger.exception("Gemini voice xatosi: %s", e)
        raise
