from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('portal_api', '0003_portaltemplate_login_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='portaltemplate',
            name='login_type',
        ),
    ]
