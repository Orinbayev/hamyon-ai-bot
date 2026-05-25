from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debt import Debt, DebtStatus
from app.repositories.base import BaseRepository


class DebtRepository(BaseRepository[Debt]):
    model = Debt

    async def get_by_id_for_user(self, debt_id: int, user_id: int) -> Debt | None:
        """Faqat shu foydalanuvchiga tegishli qarzni qaytaradi."""
        result = await self.session.execute(
            select(Debt).where(
                and_(
                    Debt.id == debt_id,
                    Debt.user_id == user_id,  # ← MAJBURIY user isolation
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_active_for_user(self, user_id: int) -> list[Debt]:
        """Shu foydalanuvchining faol qarzlari."""
        result = await self.session.execute(
            select(Debt)
            .where(
                and_(
                    Debt.user_id == user_id,  # ← MAJBURIY user isolation
                    Debt.status == DebtStatus.ACTIVE,
                )
            )
            .order_by(desc(Debt.created_at))
        )
        return list(result.scalars())

    async def get_all_for_user(self, user_id: int) -> list[Debt]:
        """Shu foydalanuvchining barcha qarzlari."""
        result = await self.session.execute(
            select(Debt)
            .where(Debt.user_id == user_id)  # ← MAJBURIY user isolation
            .order_by(desc(Debt.created_at))
        )
        return list(result.scalars())

    async def create_for_user(self, user_id: int, **kwargs) -> Debt:
        """Qarz yaratishda user_id MAJBURIY."""
        return await self.create(user_id=user_id, **kwargs)

    async def mark_paid(self, debt_id: int, user_id: int) -> Debt | None:
        """Faqat o'z qarzini to'langan deb belgilaydi."""
        debt = await self.get_by_id_for_user(debt_id, user_id)
        if not debt:
            return None
        debt.status = DebtStatus.PAID
        debt.paid_amount = debt.amount
        await self.session.flush()
        await self.commit()
        return debt
