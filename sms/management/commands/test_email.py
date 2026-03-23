from django.core.management.base import BaseCommand
from sms.services.email_gateway import send_email
from sms.models import EmailProvider


class Command(BaseCommand):
    help = 'Test Resend email sending'

    def add_arguments(self, parser):
        parser.add_argument('--to', type=str, default='ssebalekejohn@gmail.com')

    def handle(self, *args, **options):
        to_email = options['to']

        provider = EmailProvider.objects.filter(is_active=True).first()
        if not provider:
            self.stderr.write('ERROR: No active email provider found')
            return

        self.stdout.write(f'Provider: {provider.name}')
        self.stdout.write(f'From: {provider.from_email}')
        self.stdout.write(f'API Key prefix: {provider.api_key[:12]}...')
        self.stdout.write(f'Sending to: {to_email}')

        ok, resp = send_email(
            to_email=to_email,
            subject='SpotPay Test Email',
            html='<p>This is a test email from SpotPay. Resend is working!</p>',
            text='This is a test email from SpotPay. Resend is working!',
        )

        if ok:
            self.stdout.write(self.style.SUCCESS(f'SUCCESS: {resp}'))
        else:
            self.stderr.write(f'FAILED: {resp}')
