from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallets', '0003_withdrawalrequest_payout_method_and_more'),
    ]

    operations = [
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
