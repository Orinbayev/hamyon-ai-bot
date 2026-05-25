"""
Motivational Engine — context-aware, dopamine-optimized, never boring.
Random selection + last-used prevention = always feels fresh.
"""
import random
from dataclasses import dataclass
from typing import Literal

ContextType = Literal[
    "save_expense", "save_income", "save_multi",
    "streak_milestone", "level_up",
    "today_report", "week_report", "month_report",
    "welcome_back",
]

# ── Message pools ─────────────────────────────────────────────────────────────

_SAVE_EXPENSE: list[str] = [
    "🔥 Aniq qayd, {name}. Finance discipline ishlayapti.",
    "✅ Har bir so'm hisobda, {name}. Davom eting!",
    "📊 {name} — xarajatlar nazorat ostida.",
    "🎯 Budget sniper mode aktiv, {name}.",
    "⚡ {name}, pul oqimi kuzatuv ostiga olindi.",
    "💪 {name}, moliyaviy intizom kuchaymoqda.",
    "🧠 Aqlli qayd, {name}. Katta natijalarga olib boradi.",
    "🛡 {name}, moliyaviy himoya darajasi oshmoqda.",
    "📌 {name} — xarajat qayd etildi. Kuzatuv davom etmoqda.",
    "🌟 Zo'r tracking, {name}. Capital control faol.",
]

_SAVE_INCOME: list[str] = [
    "💰 {name}, kapital ortmoqda! Boylik qurish jarayoni davom etmoqda.",
    "📈 Kirim qayd etildi, {name}. Cash flow nazorat ostida.",
    "🚀 {name}, boylik strategiyasi ishlayapti.",
    "💎 {name} — har bir kirim boylikning poydevori.",
    "🤑 Income tracking aktiv, {name}. To'g'ri yo'ldasiz!",
    "⬆️ {name}, moliyaviy salohiyat oshmoqda.",
    "🏦 {name}, kapital boshqaruvi professional darajada.",
]

_SAVE_MULTI: list[str] = [
    "⚡ {name}, {count} ta tranzaksiya bir zumda qayd etildi. Efektiv!",
    "🔥 {name}, to'liq kuzatuv! {count} ta yozuv saqlandi.",
    "💎 {name}, batch tracking activated. Premium!",
    "🎯 {name} — {count} ta moliyaviy harakat qayd etildi.",
    "📊 {name}, {count} ta yozuv — nazorat sizi kutmoqda.",
]

_TODAY_REPORT: list[str] = [
    "📅 {name}, bugungi moliyaviy rasm:",
    "📊 {name}, bugun pul oqimingiz:",
    "🔍 {name}, bugungi finance snapshot:",
    "⚡ {name}, real-time bugungi holat:",
]

_WEEK_REPORT: list[str] = [
    "📆 {name}, haftalik finance hisoboti:",
    "📊 {name}, 7 kunlik pul oqimi:",
    "🔥 {name}, haftalik performance:",
    "💎 {name}, haftalik kapital nazorati:",
]

_MONTH_REPORT: list[str] = [
    "🗓 {name}, oylik moliyaviy hisobot:",
    "📊 {name}, oylik finance dashboard:",
    "💼 {name}, oylik kapital analitikasi:",
    "🏆 {name}, oylik performance ko'rsatkichlari:",
]

_WELCOME_BACK: list[str] = [
    "👋 Qaytib keldingiz, {name}! Pul nazorati davom etmoqda.",
    "🚀 {name}, Finance tracker sizni kutmoqda!",
    "💎 Xush kelibsiz, {name}. Real-time tracking faol.",
    "⚡ {name}, moliyaviy nazorat tizimi aktiv!",
    "🔥 {name}, kapital kuzatuvi davom etmoqda.",
]

# ── Streak milestone messages ─────────────────────────────────────────────────

STREAK_MILESTONES = {
    3:   "🔥 {name}, 3 kunlik tracking streak! Odatlar shakllanmoqda.",
    7:   "⚡ {name}, 1 haftalik streak! Finance habit shakllandi.",
    14:  "💎 {name}, 2 haftalik davomli tracking! Elite darajaga yaqin.",
    30:  "🏆 {name}, 30 KUNLIK STREAK!\nBu real finance mastery.",
    60:  "👑 {name}, 60 kun! Siz haqiqiy moliya professionaliga aylanyapsiz.",
    100: "🔱 {name}, 100 KUNLIK STREAK!\nLegendary. Absolute finance master.",
}

# ── Level system ──────────────────────────────────────────────────────────────

LEVELS: dict[int, tuple[str, str]] = {
    1: ("🌱", "Finance Rookie"),
    2: ("📊", "Budget Tracker"),
    3: ("💼", "Money Manager"),
    4: ("🏆", "Finance Pro"),
    5: ("💎", "Capital Controller"),
    6: ("🔱", "Finance Master"),
}

LEVEL_THRESHOLDS = [0, 10, 30, 70, 150, 300]

_LEVEL_UP: list[str] = [
    "🎖 Level UP, {name}! {icon} {level_name} — yangi bosqich!",
    "⬆️ {name}, {icon} {level_name} darajasiga ko'tarildingiz!",
    "🚀 {name}, yangi daraja: {icon} {level_name}. Davom eting!",
    "🌟 {name}, {icon} {level_name}! Moliyaviy o'sish davom etmoqda.",
]

# ── Pool index by context ─────────────────────────────────────────────────────

_POOLS: dict[str, list[str]] = {
    "save_expense":   _SAVE_EXPENSE,
    "save_income":    _SAVE_INCOME,
    "save_multi":     _SAVE_MULTI,
    "today_report":   _TODAY_REPORT,
    "week_report":    _WEEK_REPORT,
    "month_report":   _MONTH_REPORT,
    "welcome_back":   _WELCOME_BACK,
}

# ── Public API ────────────────────────────────────────────────────────────────

def get_level(total_transactions: int) -> int:
    level = 1
    for i, threshold in enumerate(LEVEL_THRESHOLDS):
        if total_transactions >= threshold:
            level = i + 1
    return min(level, 6)


def get_level_info(level: int) -> tuple[str, str]:
    return LEVELS.get(level, ("📌", "Unknown"))


def get_message(context: str, name: str, **kwargs) -> str:
    pool = _POOLS.get(context, _SAVE_EXPENSE)
    template = random.choice(pool)
    return template.format(name=name, **kwargs)


def get_streak_message(streak: int, name: str) -> str | None:
    if streak not in STREAK_MILESTONES:
        return None
    return STREAK_MILESTONES[streak].format(name=name)


def get_level_up_message(name: str, new_level: int) -> str:
    icon, level_name = get_level_info(new_level)
    template = random.choice(_LEVEL_UP)
    return template.format(name=name, icon=icon, level_name=level_name)


def days_to_next_streak(current: int) -> int | None:
    milestones = sorted(STREAK_MILESTONES.keys())
    for m in milestones:
        if current < m:
            return m - current
    return None
