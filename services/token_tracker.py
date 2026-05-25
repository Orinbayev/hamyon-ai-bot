"""
Gemini token usage tracker — thread-safe singleton.
DB siz ishlaydi; restart bo'lsa bugungi sanani qayta boshlaydi.
"""

from dataclasses import dataclass, field
from datetime import date
from threading import Lock

# Gemini free-tier kunlik limitlar (gemini-2.5-flash)
RPD_LIMIT = 500          # requests per day
TPD_LIMIT = 1_000_000    # tokens per day
RPM_LIMIT = 10           # requests per minute


@dataclass
class _DayStats:
    day: date
    requests: int = 0
    prompt_tokens: int = 0
    response_tokens: int = 0
    total_tokens: int = 0
    model: str = ""

    @property
    def req_remaining(self) -> int:
        return max(0, RPD_LIMIT - self.requests)

    @property
    def tok_remaining(self) -> int:
        return max(0, TPD_LIMIT - self.total_tokens)

    @property
    def req_pct(self) -> float:
        return self.requests / RPD_LIMIT * 100

    @property
    def tok_pct(self) -> float:
        return self.total_tokens / TPD_LIMIT * 100


class _Tracker:
    """Module-level singleton — import qilib ishlating."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._today = _DayStats(day=date.today())
        self._session_requests = 0
        self._session_tokens = 0

    def _refresh(self) -> None:
        today = date.today()
        if self._today.day != today:
            self._today = _DayStats(day=today)

    def record(
        self,
        prompt_tokens: int,
        response_tokens: int,
        total_tokens: int,
        model: str = "",
    ) -> None:
        with self._lock:
            self._refresh()
            self._today.requests += 1
            self._today.prompt_tokens += prompt_tokens
            self._today.response_tokens += response_tokens
            self._today.total_tokens += total_tokens
            if model:
                self._today.model = model
            self._session_requests += 1
            self._session_tokens += total_tokens

    def stats(self) -> _DayStats:
        with self._lock:
            self._refresh()
            return self._today

    @property
    def session_requests(self) -> int:
        return self._session_requests

    @property
    def session_tokens(self) -> int:
        return self._session_tokens


tracker = _Tracker()
