from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0007_alter_paymentsystemconfig_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentprovider',
            name='api_key',
            field=models.CharField(max_length=500),
        ),
        migrations.AlterField(
            model_name='paymentprovider',
            name='api_secret',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AlterField(
            model_name='payment',
            name='provider_reference',
            field=models.CharField(blank=True, max_length=500, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='payment',
            name='external_reference',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='payment',
            name='processor_message',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
    ]
