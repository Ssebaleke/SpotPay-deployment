from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0008_increase_char_field_lengths'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentprovider',
            name='base_url',
            field=models.URLField(blank=True),
        ),
    ]
