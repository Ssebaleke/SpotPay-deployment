# Generated migration for adding webhook_secret field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0011_add_livepay_provider_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentprovider',
            name='webhook_secret',
            field=models.CharField(
                blank=True,
                help_text='Webhook secret key for signature verification (LivePay, KwaPay, etc.)',
                max_length=500
            ),
        ),
    ]