from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RequiredChannel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel_id", models.BigIntegerField(unique=True, verbose_name="Kanal ID")),
                ("username", models.CharField(blank=True, max_length=255, verbose_name="@username")),
                ("title", models.CharField(max_length=255, verbose_name="Kanal nomi")),
                ("invite_link", models.URLField(blank=True, verbose_name="Taklif havolasi")),
                ("is_active", models.BooleanField(default=True, verbose_name="Faol")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Qo'shilgan vaqt")),
            ],
            options={
                "verbose_name": "Majburiy kanal",
                "verbose_name_plural": "Majburiy kanallar",
                "ordering": ["-created_at"],
            },
        ),
    ]
