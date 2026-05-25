from django.db import models
from apps.users.models import TelegramUser


class Category(models.Model):
    CATEGORY_TYPES = [
        ("income", "Kirim"),
        ("expense", "Chiqim"),
        ("both", "Ikkalasi"),
    ]

    name = models.CharField(max_length=100, verbose_name="Nomi")
    slug = models.CharField(max_length=100, verbose_name="Slug")
    icon = models.CharField(max_length=10, default="📌", verbose_name="Ikonka")
    type = models.CharField(max_length=10, choices=CATEGORY_TYPES, default="both", verbose_name="Turi")
    is_default = models.BooleanField(default=False, verbose_name="Standart")
    user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="categories",
        verbose_name="Foydalanuvchi",
    )

    class Meta:
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"
        ordering = ["name"]

    def __str__(self):
        return f"{self.icon} {self.name}"


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ("income", "Kirim"),
        ("expense", "Chiqim"),
    ]

    CURRENCIES = [
        ("UZS", "So'm"),
        ("USD", "Dollar"),
        ("RUB", "Rubl"),
    ]

    PAYMENT_METHODS = [
        ("cash", "Naqd"),
        ("card", "Karta"),
        ("click", "Click"),
        ("payme", "Payme"),
        ("bank", "Bank"),
        ("other", "Boshqa"),
    ]

    user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name="Foydalanuvchi",
    )
    type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, verbose_name="Turi")
    amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Summa")
    currency = models.CharField(max_length=3, choices=CURRENCIES, default="UZS", verbose_name="Valyuta")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
        verbose_name="Kategoriya",
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PAYMENT_METHODS,
        default="cash",
        verbose_name="To'lov turi",
    )
    note = models.TextField(blank=True, default="", verbose_name="Izoh")
    transaction_date = models.DateField(verbose_name="Sana")
    raw_text = models.TextField(blank=True, default="", verbose_name="Asl matn")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        verbose_name = "Tranzaksiya"
        verbose_name_plural = "Tranzaksiyalar"
        ordering = ["-transaction_date", "-created_at"]

    def __str__(self):
        type_str = "Kirim" if self.type == "income" else "Chiqim"
        return f"{type_str}: {self.amount:,.0f} {self.currency} — {self.transaction_date}"
