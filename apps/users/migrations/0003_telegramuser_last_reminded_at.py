from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_requiredchannel"),
    ]

    operations = [
        migrations.AddField(
            model_name="telegramuser",
            name="last_reminded_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Oxirgi eslatma vaqti"),
        ),
    ]
