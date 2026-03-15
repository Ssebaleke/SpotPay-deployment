from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('packages', '0001_initial'),
        ('vouchers', '0003_merge_0002'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='VoucherBatchDeletionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('batch_reference', models.PositiveBigIntegerField()),
                ('source_filename', models.CharField(blank=True, max_length=255)),
                ('vouchers_deleted_count', models.PositiveIntegerField(default=0)),
                ('deleted_at', models.DateTimeField(auto_now_add=True)),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deleted_voucher_batches', to=settings.AUTH_USER_MODEL)),
                ('package', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='batch_deletion_logs', to='packages.package')),
                ('vendor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='batch_deletion_logs', to='accounts.vendor')),
            ],
            options={
                'ordering': ['-deleted_at'],
            },
        ),
    ]
