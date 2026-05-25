"""
Engagement Service — streak, level, xp, achievements.
Har bir tranzaksiya saqlanganda chaqiriladi.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils import motivational as motive


@dataclass
class EngagementResult:
    name: str                        # display name
    streak: int                      # current streak after update
    is_new_streak_day: bool          # streak increased today?
    streak_milestone: int | None     # 3,7,14,30... hit today?
    leveled_up: bool
    old_level: int
    new_level: int
    motivational_msg: str            # main contextual message
    bonus_msg: str | None            # streak or level-up bonus line

    @property
    def streak_msg(self) -> str | None:
        if not self.streak_milestone:
            return None
        return motive.get_streak_message(self.streak_milestone, self.name)

    @property
    def level_up_msg(self) -> str | None:
        if not self.leveled_up:
            return None
        return motive.get_level_up_message(self.name, self.new_level)

    @property
    def next_streak_hint(self) -> str | None:
        if self.streak_milestone:
            return None  # already celebrated today
        days_left = motive.days_to_next_streak(self.streak)
        if days_left and 1 <= days_left <= 3:
            return f"💡 Yana {days_left} kun — keyingi milestone!"
        return None


class EngagementService:
    STREAK_MILESTONES = {3, 7, 14, 30, 60, 100}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _display_name(self, user: User) -> str:
        return user.custom_name or user.full_name.split()[0]

    async def record_activity(
        self,
        user: User,
        context: str = "save_expense",
        count: int = 1,
    ) -> EngagementResult:
        """
        Foydalanuvchi tranzaksiya saqladi → streak, xp, level yangilanadi.
        Bir kunda bir marta streak oshadi.
        """
        today = date.today()
        name = self._display_name(user)

        # ── Streak update ─────────────────────────────────────────────────────
        old_streak = user.streak_days
        is_new_streak_day = False
        streak_milestone: int | None = None

        last = user.last_activity_date
        if last is None or last < today - timedelta(days=1):
            # First ever activity OR streak broken — start fresh
            user.streak_days = 1
            is_new_streak_day = True
        elif last == today - timedelta(days=1):
            # Consecutive day!
            user.streak_days += 1
            is_new_streak_day = True
        # elif last == today: streak stays, no change

        if is_new_streak_day and user.streak_days in self.STREAK_MILESTONES:
            streak_milestone = user.streak_days

        user.last_activity_date = today
        user.total_transactions += count

        # ── Level update ──────────────────────────────────────────────────────
        old_level = user.level
        new_level = motive.get_level(user.total_transactions)
        user.level = new_level
        leveled_up = new_level > old_level

        # ── XP update ─────────────────────────────────────────────────────────
        xp_gain = count * 10
        if is_new_streak_day:
            xp_gain += user.streak_days * 2  # streak bonus
        user.xp += xp_gain

        await self.session.flush()

        # ── Motivational message ──────────────────────────────────────────────
        motivational_msg = motive.get_message(context, name, count=count)
        bonus_msg = None

        if leveled_up:
            bonus_msg = motive.get_level_up_message(name, new_level)
        elif streak_milestone:
            bonus_msg = motive.get_streak_message(streak_milestone, name)

        return EngagementResult(
            name=name,
            streak=user.streak_days,
            is_new_streak_day=is_new_streak_day,
            streak_milestone=streak_milestone,
            leveled_up=leveled_up,
            old_level=old_level,
            new_level=new_level,
            motivational_msg=motivational_msg,
            bonus_msg=bonus_msg,
        )
