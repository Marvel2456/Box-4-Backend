from django.core.management.base import BaseCommand
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Test sending an email to diagnose email configuration and delivery issues'

    def add_arguments(self, parser):
        parser.add_argument('recipient', type=str, help='Recipient email address')

    def handle(self, *args, **options):
        recipient = options['recipient']
        self.stdout.write(self.style.NOTICE("=" * 60))
        self.stdout.write(self.style.NOTICE("Box-4 Email Diagnostic Tool"))
        self.stdout.write(self.style.NOTICE("=" * 60))

        backend = getattr(settings, 'EMAIL_BACKEND', 'Not configured')
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@box4homes.com')
        resend_key = getattr(settings, 'RESEND_API_KEY', None) or os.getenv('RESEND_API_KEY')

        self.stdout.write(f"1. EMAIL_BACKEND: {backend}")
        self.stdout.write(f"2. DEFAULT_FROM_EMAIL: {from_email}")
        self.stdout.write(f"3. RESEND_API_KEY configured: {'Yes (' + resend_key[:6] + '...)' if resend_key else 'No (None)'}")

        if not resend_key:
            self.stdout.write(self.style.WARNING("\n[WARNING] RESEND_API_KEY is not set!"))
            self.stdout.write(self.style.WARNING("Django is using console.EmailBackend. Emails will only be printed to console/logs, not sent to actual inboxes."))
        
        self.stdout.write(f"\nAttempting to send test OTP email to: {recipient}...")

        try:
            from core.emails import send_otp_verification_email
            # Call with fail_silently=False so we catch the exact exception
            result = send_otp_verification_email(recipient, "1234", fail_silently=False)
            if result > 0:
                self.stdout.write(self.style.SUCCESS(f"\n[SUCCESS] Test email successfully dispatched to {recipient}!"))
            else:
                self.stdout.write(self.style.ERROR(f"\n[FAILURE] Email backend returned 0 messages sent."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n[ERROR] Failed to send email:"))
            self.stdout.write(self.style.ERROR(f"Exception Type: {type(e).__name__}"))
            self.stdout.write(self.style.ERROR(f"Exception Details: {str(e)}"))

        self.stdout.write(self.style.NOTICE("=" * 60))
