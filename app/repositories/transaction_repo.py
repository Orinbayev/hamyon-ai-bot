"""
TransactionRepository — BARCHA so'rovlar user_id bilan filtrlanadi.
Bu faylda birorta ham user_id filtrsiz so'rov YO'Q.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.category import Category
from app.models.transaction import Transaction, TransactionType
from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    model = Transaction

    # ── User-isolated read queries ────────────────────────────────────────────

    async def get_by_id_for_user(
        self, transaction_id: int, user_id: int
    ) -> Transaction | None:
        """Faqat shu foydalanuvchiga tegishli tranzaksiyani qaytaradi."""
        result = await self.session.execute(
            select(Transaction)
            .options(joinedload(Transaction.category))
            .where(
                and_(
                    Transaction.id == transaction_id,
                    Transaction.user_id == user_id,  # ← MAJBURIY user isolation
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_last_for_user(self, user_id: int) -> Transaction | None:
        """Shu foydalanuvchining eng oxirgi tranzaksiyasi."""
        result = await self.session.execute(
            select(Transaction)
            .options(joinedload(Transaction.category))
            .where(Transaction.user_id == user_id)  # ← MAJBURIY user isolation
            .order_by(desc(Transaction.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_recent_for_user(
        self, user_id: int, limit: int = 20
    ) -> list[Transaction]:
        """Shu foydalanuvchining oxirgi N ta tranzaksiyasi."""
        result = await self.session.execute(
            select(Transaction)
            .options(joinedload(Transaction.category))
            .where(Transaction.user_id == user_id)  # ← MAJBURIY user isolation
            .order_by(desc(Transaction.transaction_date), desc(Transaction.created_at))
            .limit(limit)
        )
        return list(result.scalars().unique())

    async def get_by_period_for_user(
        self,
        user_id: int,
        start: date,
        end: date,
        tx_type: TransactionType | None = None,
    ) -> list[Transaction]:
        """Shu foydalanuvchining berilgan davr tranzaksiyalari."""
        conditions = [
            Transaction.user_id == user_id,  # ← MAJBURIY user isolation
            Transaction.transaction_date >= start,
            Transaction.transaction_date <= end,
        ]
        if tx_type:
            conditions.append(Transaction.type == tx_type)

        result = await self.session.execute(
            select(Transaction)
            .options(joinedload(Transaction.category))
            .where(and_(*conditions))
            .order_by(desc(Transaction.transaction_date), desc(Transaction.created_at))
        )
        return list(result.scalars().unique())

    async def get_sum_for_user(
        self,
        user_id: int,
        start: date,
        end: date,
        tx_type: TransactionType,
    ) -> Decimal:
        """Shu foydalanuvchining berilgan davr summasi."""
        result = await self.session.execute(
            select(func.sum(Transaction.amount)).where(
                and_(
                    Transaction.user_id == user_id,  # ← MAJBURIY user isolation
                    Transaction.transaction_date >= start,
                    Transaction.transaction_date <= end,
                    Transaction.type == tx_type,
                )
            )
        )
        return result.scalar_one_or_none() or Decimal("0")

    async def get_category_stats_for_user(
        self,
        user_id: int,
        start: date,
        end: date,
    ) -> list[dict]:
        """Shu foydalanuvchining kategoriya bo'yicha statistikasi."""
        result = await self.session.execute(
            select(
                Category.name,
                Category.slug,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("count"),
            )
            .join(Category, Transaction.category_id == Category.id, isouter=True)
            .where(
                and_(
                    Transaction.user_id == user_id,  # ← MAJBURIY user isolation
                    Transaction.transaction_date >= start,
                    Transaction.transaction_date <= end,
                    Transaction.type == TransactionType.EXPENSE,
                )
            )
            .group_by(Category.name, Category.slug)
            .order_by(desc("total"))
        )
        return [
            {
                "name": row.name or "Boshqa",
                "slug": row.slug or "boshqa",
                "total": row.total or Decimal("0"),
                "count": row.count,
            }
            for row in result
        ]

    async def get_for_export(
        self,
        user_id: int,
        start: date | None,
        end: date | None,
    ) -> list[Transaction]:
        """Eksport uchun shu foydalanuvchining tranzaksiyalari."""
        conditions = [Transaction.user_id == user_id]  # ← MAJBURIY user isolation
        if start:
            conditions.append(Transaction.transaction_date >= start)
        if end:
            conditions.append(Transaction.transaction_date <= end)

        result = await self.session.execute(
            select(Transaction)
            .options(joinedload(Transaction.category))
            .where(and_(*conditions))
            .order_by(desc(Transaction.transaction_date), desc(Transaction.created_at))
        )
        return list(result.scalars().unique())

    # ── User-isolated write queries ───────────────────────────────────────────

    async def create_for_user(self, user_id: int, **kwargs) -> Transaction:
        """Tranzaksiya yaratishda user_id MAJBURIY."""
        return await self.create(user_id=user_id, **kwargs)

    async def delete_for_user(self, transaction_id: int, user_id: int) -> bool:
        """Faqat o'z tranzaksiyasini o'chira oladi."""
        tx = await self.get_by_id_for_user(transaction_id, user_id)
        if not tx:
            return False  # Boshqa userning tranzaksiyasi — rad etiladi
        await self.session.delete(tx)
        await self.commit()
        return True

    async def delete_all_for_user(self, user_id: int) -> int:
        """Shu foydalanuvchining BARCHA tranzaksiyalarini o'chiradi. O'chirilgan sonini qaytaradi."""
        result = await self.session.execute(
            delete(Transaction).where(Transaction.user_id == user_id)  # ← MAJBURIY user isolation
        )
        await self.commit()
        return result.rowcount

    async def count_for_user(self, user_id: int) -> int:
        """Shu foydalanuvchining tranzaksiyalar soni."""
        result = await self.session.execute(
            select(func.count(Transaction.id)).where(Transaction.user_id == user_id)
        )
        return result.scalar_one() or 0
