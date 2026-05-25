from django.contrib import admin

from .models import Category, Transaction


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("icon", "name", "slug", "type", "is_default", "user")
    list_filter = ("type", "is_default")
    search_fields = ("name", "slug")
    ordering = ("name",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "type_display", "amount_display",
        "category", "payment_method", "transaction_date", "created_at",
    )
    list_filter = ("type", "currency", "payment_method", "transaction_date", "category")
    search_fields = ("user__full_name", "user__telegram_id", "note", "raw_text")
    readonly_fields = ("created_at", "updated_at", "raw_text")
    date_hierarchy = "transaction_date"
    ordering = ("-transaction_date", "-created_at")
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "category")

    @admin.display(description="Turi", ordering="type")
    def type_display(self, obj):
        return "💰 Kirim" if obj.type == "income" else "💸 Chiqim"

    @admin.display(description="Summa", ordering="amount")
    def amount_display(self, obj):
        return f"{float(obj.amount):,.0f}".replace(",", " ") + f" {obj.currency}"
