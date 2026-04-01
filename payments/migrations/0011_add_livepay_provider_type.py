from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0010_add_gateway_fee_to_provider_and_split'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentprovider',
            name='transaction_pin',
            field=models.CharField(
                blank=True,
                help_text='Transaction PIN (required for LivePay Send Money)',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='paymentprovider',
            name='provider_type',
            field=models.CharField(
                choices=[
                    ('MOMO', 'Mobile Money (MakyPay)'),
                    ('CARD', 'Card / Gateway'),
                    ('YOO', 'Mobile Money (YooPay)'),
                    ('KWA', 'Mobile Money (KwaPay)'),
                    ('LIVE', 'Mobile Money (LivePay)'),
                ],
                max_length=10,
            ),
        ),
    ]
