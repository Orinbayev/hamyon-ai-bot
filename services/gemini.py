"""
Gemini AI service — google-genai SDK, to'liq async, model fallback bilan.
"""

import asyncio
import json
import logging
from datetime import date, timedelta

# aiohttp 3.9.x da ClientConnectorDNSError yo'q — google-genai SDK bug workaround
try:
    import aiohttp as _aiohttp
    if not hasattr(_aiohttp, "ClientConnectorDNSError"):
        _aiohttp.ClientConnectorDNSError = _aiohttp.ClientConnectorError
except Exception:
    pass

from google import genai
from google.genai import types
from django.conf import settings

from services.token_tracker import tracker

logger = logging.getLogger("services")

client = genai.Client(api_key=settings.GEMINI_API_KEY)

MODEL = settings.GEMINI_MODEL

# Matn uchun fallback modellar
FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]

# Audio uchun faqat tasdiqlangan modellar (yangi API key lar uchun)
VOICE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
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
    return any(code in msg for code in (
        "429", "404", "500", "503",
        "RESOURCE_EXHAUSTED", "NOT_FOUND", "UNAVAILABLE", "INTERNAL",
    ))


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


def _parse_voice_response(raw: str) -> tuple[list[dict], str]:
    """Parse structured voice response: TRANSCRIPTION: ... JSON: [...]"""
    transcription = ""
    json_text = raw

    if "TRANSCRIPTION:" in raw:
        parts = raw.split("TRANSCRIPTION:", 1)[1]
        if "JSON:" in parts:
            transcription = parts.split("JSON:")[0].strip()
            json_text = parts.split("JSON:", 1)[1].strip()
        else:
            transcription = parts.strip()
            json_text = "[]"
    elif "JSON:" in raw:
        json_text = raw.split("JSON:", 1)[1].strip()

    try:
        items = _parse_items(json_text)
    except (json.JSONDecodeError, Exception):
        items = []

    return items, transcription


async def _call_voice(contents, config: types.GenerateContentConfig) -> str:
    """Voice uchun call: 503 bo'lsa 3 marta 4s interval bilan qayta urinadi."""
    models_to_try = [MODEL] + [m for m in VOICE_MODELS if m != MODEL]

    # 2 ta urinish: darhol, 3s kutib (503 qisqa vaqtinchalik bo'lsa yetarli)
    for attempt in range(2):
        if attempt > 0:
            logger.info("Voice 503, 3s kutilmoqda (2-urinish)...")
            await asyncio.sleep(3)

        last_err: Exception | None = None
        for model_name in models_to_try:
            try:
                response = await client.aio.models.generate_content(
                    model=model_name, contents=contents, config=config,
                )
                if model_name != MODEL or attempt > 0:
                    logger.info("Voice model: %s (attempt %d)", model_name, attempt + 1)
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
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    logger.warning("Voice model %s: 503 (attempt %d)", model_name, attempt + 1)
                    last_err = e
                elif _is_quota_error(e):
                    logger.warning("Voice model %s ishlamadi: %s", model_name, err_str[:80])
                    last_err = e
                else:
                    raise

        if last_err and ("503" not in str(last_err) and "UNAVAILABLE" not in str(last_err)):
            break  # 503 emas — retry foyda bermaydi

    raise last_err or RuntimeError("Barcha voice modellari ishlamadi")


def is_503_error(err: Exception) -> bool:
    msg = str(err)
    return "503" in msg or "UNAVAILABLE" in msg


async def parse_voice(audio_bytes: bytes, mime_type: str = "audio/ogg") -> tuple[list[dict], str]:
    """
    Returns (transactions, transcription_text).
    Pipeline: Groq Whisper (ishonchli) → Gemini text parser.
    Fallback: Gemini audio (agar GROQ_API_KEY yo'q bo'lsa).
    """
    from django.conf import settings as _settings
    from services import stt as stt_service

    groq_key = getattr(_settings, "GROQ_API_KEY", "")
    if groq_key:
        try:
            transcription = await stt_service.transcribe(audio_bytes, mime_type)
            if transcription:
                logger.info("Groq transcript: %s", transcription[:80])
                items = await parse_text(transcription)
                return items, transcription
            return [], ""
        except ValueError:
            pass  # GROQ_API_KEY yo'q — fallbackga o'tish
        except Exception as e:
            logger.warning("Groq STT xatosi, Gemini audio ga o'tilmoqda: %s", e)

    # Fallback: Gemini audio (503 bo'lishi mumkin)
    prompt = (
        "Ovozda moliyaviy xabar bor. Shovqin yoki shamol bo'lsa ham eshitilganini yoz.\n"
        "Javob formati:\n"
        "TRANSCRIPTION: <eshitilgan o'zbek matni>\n"
        "JSON: <tranzaksiyalar array yoki []>"
    )
    contents = [
        types.Part(inline_data=types.Blob(data=audio_bytes, mime_type=mime_type)),
        prompt,
    ]
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.25,
    )
    try:
        raw = await _call_voice(contents, config)
        return _parse_voice_response(raw)
    except Exception as e:
        logger.exception("Gemini voice xatosi: %s", e)
        raise
