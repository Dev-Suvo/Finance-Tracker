import smtplib

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError

from tracker.views import send_email_sendgrid


class Command(BaseCommand):
    help = 'Send a test email right now and print the exact result (never prints secrets).'

    def add_arguments(self, parser):
        parser.add_argument('recipient', help='Address to send the test message to')

    def handle(self, *args, **options):
        to = options['recipient']
        host = settings.EMAIL_HOST
        primary = int(settings.EMAIL_PORT or 587)
        fallback = 465 if primary != 465 else 587
        self.stdout.write(
            f'config: backend={settings.EMAIL_BACKEND} host={host} port={primary} '
            f'tls={settings.EMAIL_USE_TLS} '
            f'user={"set" if settings.EMAIL_HOST_USER else "EMPTY"} '
            f'pass={"set" if settings.EMAIL_HOST_PASSWORD else "EMPTY"} '
            f'sendgrid_api={"set" if settings.SENDGRID_API_KEY else "EMPTY"}'
        )

        msg = EmailMultiAlternatives(
            'FinanceTracker SMTP test',
            'If this message arrived, email delivery from this server works.',
            settings.DEFAULT_FROM_EMAIL,
            [to],
        )

        # HTTPS API path: the only one that works on Render FREE (SMTP blocked).
        if settings.SENDGRID_API_KEY:
            self.stdout.write('using SendGrid HTTPS API (port 443) ...')
            try:
                send_email_sendgrid(msg)
            except Exception as exc:
                raise CommandError(f'email NOT sent via SendGrid: {type(exc).__name__}: {exc}')
            self.stdout.write(self.style.SUCCESS(f'SENT to {to} via SendGrid API (HTTPS)'))
            return

        last_error = None
        for port in (primary, fallback):
            try:
                self.stdout.write(f'attempting {host}:{port} ...')
                if port == 465:
                    conn = smtplib.SMTP_SSL(host, port, timeout=settings.EMAIL_TIMEOUT or 15)
                else:
                    conn = smtplib.SMTP(host, port, timeout=settings.EMAIL_TIMEOUT or 15)
                    conn.starttls()
                try:
                    conn.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
                    self.stdout.write('login OK')
                    conn.sendmail(msg.from_email, msg.to, msg.message().as_string())
                finally:
                    conn.close()
                self.stdout.write(self.style.SUCCESS(f'SENT to {to} via {host}:{port}'))
                return
            except Exception as exc:
                last_error = exc
                self.stdout.write(self.style.WARNING(
                    f'{host}:{port} failed: {type(exc).__name__}: {exc}'))
        hint = ''
        if isinstance(last_error, OSError) and getattr(last_error, 'errno', None) == 101:
            hint = (' [Render FREE blocks outbound SMTP ports 25/465/587 - '
                    'set SENDGRID_API_KEY to send over HTTPS instead]')
        raise CommandError(
            f'email NOT sent. Last error: {type(last_error).__name__}: {last_error}.{hint}')
