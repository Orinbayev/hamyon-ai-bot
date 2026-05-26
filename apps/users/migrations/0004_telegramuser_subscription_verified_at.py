from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_telegramuser_last_reminded_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='telegramuser',
            name='subscription_verified_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Obuna tasdiqlangan vaqt'),
        ),
    ]
