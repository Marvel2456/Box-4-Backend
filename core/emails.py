import os
import resend
from django.conf import settings
from django.core.mail import send_mail

def send_email_via_resend(to, subject, html_content=None, text_content=None, from_email=None, fail_silently=False):
    """
    Direct helper to send an email via Resend SDK.
    """
    api_key = getattr(settings, 'RESEND_API_KEY', None) or os.getenv('RESEND_API_KEY')
    if not api_key:
        if not fail_silently:
            raise ValueError("RESEND_API_KEY environment variable or setting is missing.")
        return None

    resend.api_key = api_key
    sender = from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'onboarding@resend.dev')

    recipients = [to] if isinstance(to, str) else list(to)

    params = {
        "from": sender,
        "to": recipients,
        "subject": subject,
    }

    if html_content:
        params["html"] = html_content
    if text_content:
        params["text"] = text_content
    if not html_content and not text_content:
        params["text"] = ""

    try:
        return resend.Emails.send(params)
    except Exception as e:
        if not fail_silently:
            raise e
        return None
