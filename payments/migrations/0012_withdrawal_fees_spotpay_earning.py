from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0011_add_livepay_provider_type'),
        ('wallets', '0003_withdrawalrequest_payout_method_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentsystemconfig',
            name='withdrawal_gateway_fee_percentage',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Gateway fee % charged by payment provider on withdrawals (e.g. 3)',
                max_digits=5,
            ),
        ),
        migrations.AddField(
            model_name='paymentsystemconfig',
            name='withdrawal_spotpay_fee_percentage',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='SpotPay fee % charged on vendor withdrawals (e.g. 2)',
                max_digits=5,
            ),
        ),
        migrations.CreateModel(
            name='SpotPayEarning',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(
                    choices=[
                        ('COMMISSION', 'Transaction Commission'),
                        ('SUBSCRIPTION', 'Subscription Payment'),
                        ('SMS_PURCHASE', 'SMS Purchase'),
                        ('WITHDRAWAL_FEE', 'Withdrawal Fee'),
                    ],
                    max_length=20,
                )),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('reference', models.CharField(max_length=100, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
