#!/bin/sh
# Write all env vars to a file that cron jobs can use
python3 -c "
import os
with open('/app/.cronenv', 'w') as f:
    for k, v in os.environ.items():
        # skip vars with newlines
        if '\n' not in v and '\r' not in v:
            f.write(f'export {k}={repr(v)}\n')
"

touch /var/log/cron.log

cat > /etc/cron.d/spotpay << 'EOF'
0 6 * * * root /usr/local/bin/django-cron enforce_subscriptions >> /var/log/cron.log 2>&1
*/2 * * * * root /usr/local/bin/django-cron verify_kwa_payments >> /var/log/cron.log 2>&1
* * * * * root /usr/local/bin/django-cron verify_live_payments >> /var/log/cron.log 2>&1
* * * * * root sleep 30 && /usr/local/bin/django-cron verify_live_payments >> /var/log/cron.log 2>&1
*/5 * * * * root /usr/local/bin/django-cron fix_missing_vouchers >> /var/log/cron.log 2>&1
*/5 * * * * root /usr/local/bin/django-cron retry_voucher_sms >> /var/log/cron.log 2>&1

EOF

chmod 0644 /etc/cron.d/spotpay
cron
tail -f /var/log/cron.log
