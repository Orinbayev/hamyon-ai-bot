from django.db import models


class RequiredChannel(models.Model):
    """Botdan foydalanish uchun obuna bo'lish kerak bo'lgan kanallar."""

    channel_id = models.BigIntegerField(unique=True, verbose_name="Kanal ID")
    username = models.CharField(max_length=255, blank=True, verbose_name="@username")
    title = models.CharField(max_length=255, verbose_name="Kanal nomi")
    invite_link = models.URLField(blank=True, verbose_name="Taklif havolasi")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Qo'shilgan vaqt")

    class Meta:
        verbose_name = "Majburiy kanal"
        verbose_name_plural = "Majburiy kanallar"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.channel_id})"

    @property
    def link(self) -> str:
        if self.username:
            return f"https://t.me/{self.username.lstrip('@')}"
        return self.invite_link or ""

    @property
    def display(self) -> str:
        tag = f"@{self.username}" if self.username else f"ID: {self.channel_id}"
        status = "✅" if self.is_active else "⏸"
        return f"{status} {self.title}  <i>{tag}</i>"


class TelegramUser(models.Model):
    telegram_id = models.BigIntegerField(unique=True, verbose_name="Telegram ID")
    full_name = models.CharField(max_length=255, verbose_name="To'liq ism")
    username = models.CharField(max_length=255, null=True, blank=True, verbose_name="Username")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Qo'shilgan vaqt")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.telegram_id})"
