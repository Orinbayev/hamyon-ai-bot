from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    # ── Core identity ─────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Personalization ───────────────────────────────────────────────────────
    # Foydalanuvchi tanlagan ism (onboarding paytida so'raladi)
    custom_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Gamification ─────────────────────────────────────────────────────────
    streak_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_activity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    xp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Relationships — lazy="noload" so queries are always explicit ──────────
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="noload"
    )
    categories: Mapped[list["Category"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="noload"
    )
    debts: Mapped[list["Debt"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="noload"
    )

    @property
    def display_name(self) -> str:
        """Bot xabarlarida ko'rinadigan ism."""
        return self.custom_name or self.full_name.split()[0]

    @property
    def level_info(self) -> tuple[str, str]:
        from app.utils.motivational import get_level_info
        return get_level_info(self.level)

    def __repr__(self) -> str:
        return f"<User tg={self.telegram_id} name={self.custom_name or self.full_name!r}>"
