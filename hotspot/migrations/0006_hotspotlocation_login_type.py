from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotspot', '0005_hotspotlocation_hotspot_dns_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='hotspotlocation',
            name='login_type',
            field=models.CharField(
                choices=[
                    ('PLAIN', 'Plain \u2014 username = password (Mikhmon default)'),
                    ('CHAP', 'CHAP MD5 \u2014 username \u2260 password (KaWifi style)'),
                    ('SEPARATE', 'Separate username & password fields'),
                ],
                default='PLAIN',
                help_text='How voucher authentication works on this MikroTik',
                max_length=10,
            ),
        ),
    ]
