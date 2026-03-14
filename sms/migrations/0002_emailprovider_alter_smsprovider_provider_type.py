from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sms', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50)),
                ('provider_type', models.CharField(choices=[('RESEND', 'Resend'), ('OTHER', 'Other')], default='RESEND', max_length=20)),
                ('api_key', models.CharField(max_length=255)),
                ('from_email', models.EmailField(help_text='Verified sender email/domain in provider', max_length=254)),
                ('is_active', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AlterField(
            model_name='smsprovider',
            name='provider_type',
            field=models.CharField(choices=[('UGSMS', 'UGSMS'), ('AFRICASTALKING', "Africa's Talking"), ('YOUGANDA', 'Yo! Uganda'), ('TWILIO', 'Twilio'), ('OTHER', 'Other')], max_length=30),
        ),
    ]
