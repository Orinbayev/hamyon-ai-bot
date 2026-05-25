import logging
from datetime import date

from app.models.transaction import Transaction
from app.repositories.category_repo import CategoryRepository
from app.repositories.transaction_repo import TransactionRepository
from app.schemas.transaction import TransactionItem

logger = logging.getLogger("services")


class TransactionService:
    """
    Biznes-logika — handler to'g'ridan-to'g'ri DB bilan ishlamaydi,
    faqat shu servis orqali ishlaydi.
    """

    def __init__(
        self,
        transaction_repo: TransactionRepository,
        category_repo: CategoryRepository,
    ) -> None:
        self.tx_repo = transaction_repo
        self.cat_repo = category_repo

    async def save_from_ai(
        self,
        user_id: int,
        items: list[TransactionItem],
        raw_text: str,
    ) -> list[Transaction]:
        """AI dan kelgan tranzaksiyalarni saqlaydi. user_id MAJBURIY."""
        saved: list[Transaction] = []

        for item in items:
            try:
                category = await self.cat_repo.get_or_create_for_user(
                    user_id=user_id,
                    slug=item.category,
                    tx_type=item.type,
                )
                tx = await self.tx_repo.create_for_user(
                    user_id=user_id,
                    type=item.type,
                    amount=item.amount,
                    currency=item.currency,
                    category_id=category.id,
                    payment_method=item.payment_method,
                    note=item.note,
                    transaction_date=item.transaction_date,
                    raw_text=raw_text,
                )
                saved.append(tx)
            except Exception as e:
                logger.exception("Tranzaksiya saqlash xatosi: %s", e)

        if saved:
            await self.tx_repo.commit()

        return saved

    async def delete_last(self, user_id: int) -> Transaction | None:
        """Oxirgi tranzaksiyani o'chiradi — faqat o'zining."""
        tx = await self.tx_repo.get_last_for_user(user_id)
        if not tx:
            return None
        await self.tx_repo.delete_for_user(tx.id, user_id)
        return tx

    async def delete_by_id(self, transaction_id: int, user_id: int) -> bool:
        """ID bo'yicha o'chiradi — faqat o'z tranzaksiyasini."""
        return await self.tx_repo.delete_for_user(transaction_id, user_id)

    async def get_last(self, user_id: int) -> Transaction | None:
        return await self.tx_repo.get_last_for_user(user_id)

    async def get_recent(self, user_id: int, limit: int = 20) -> list[Transaction]:
        return await self.tx_repo.get_recent_for_user(user_id, limit)
