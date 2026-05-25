from django.contrib import admin
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.transactions.models import Transaction
from .models import TelegramUser


class TransactionInline(admin.TabularInline):
    model = Transaction
    fields = ("type", "amount", "currency", "category", "payment_method", "transaction_date", "note")
    readonly_fields = ("type", "amount", "currency", "category", "payment_method", "transaction_date", "note")
    extra = 0
    max_num = 0
    can_delete = True
    ordering = ("-transaction_date", "-created_at")
    show_change_link = True


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = (
        "telegram_id", "full_name", "username", "is_active",
        "tx_count", "income_display", "expense_display", "balance_display",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("telegram_id", "full_name", "username")
    readonly_fields = ("telegram_id", "created_at", "updated_at")
    ordering = ("-created_at",)
    inlines = [TransactionInline]
    actions = ["clear_all_transactions"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            _tx_count=Count("transactions"),
            _income=Coalesce(
                Sum("transactions__amount", filter=Q(transactions__type="income")),
                Value(0), output_field=DecimalField(),
            ),
            _expense=Coalesce(
                Sum("transactions__amount", filter=Q(transactions__type="expense")),
                Value(0), output_field=DecimalField(),
            ),
        )

    @admin.display(description="Tranzaksiyalar", ordering="_tx_count")
    def tx_count(self, obj):
        return obj._tx_count

    @admin.display(description="Kirim", ordering="_income")
    def income_display(self, obj):
        return f"+{float(obj._income):,.0f}".replace(",", " ") + " so'm"

    @admin.display(description="Chiqim", ordering="_expense")
    def expense_display(self, obj):
        return f"{float(obj._expense):,.0f}".replace(",", " ") + " so'm"

    @admin.display(description="Balans")
    def balance_display(self, obj):
        bal = float(obj._income) - float(obj._expense)
        sign = "+" if bal >= 0 else "–"
        return f"{sign}{abs(bal):,.0f}".replace(",", " ") + " so'm"

    @admin.action(description="Tanlangan foydalanuvchilarning barcha tarixini tozalash")
    def clear_all_transactions(self, request, queryset):
        user_ids = list(queryset.values_list("id", flat=True))
        deleted, _ = Transaction.objects.filter(user_id__in=user_ids).delete()
        self.message_user(request, f"✅ {deleted} ta tranzaksiya o'chirildi.")
