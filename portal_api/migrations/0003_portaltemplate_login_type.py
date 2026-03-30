from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portal_api', '0002_portaltemplate_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='portaltemplate',
            name='login_type',
            field=models.CharField(
                choices=[
                    ('PLAIN', 'Plain (username = password)'),
                    ('CHAP', 'CHAP MD5 (username \u2260 password)'),
                    ('SEPARATE', 'Separate username & password'),
                ],
                default='PLAIN',
                max_length=10,
            ),
        ),
    ]
