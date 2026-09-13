import os
import logging
import resend
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings

logger = logging.getLogger(__name__)

class ResendEmailBackend(BaseEmailBackend):
    """
    Custom Django Email Backend powered by Resend API.
    Routes all standard Django send_mail(), EmailMessage, and EmailMultiAlternatives calls through Resend.
    """
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, 'RESEND_API_KEY', None) or os.getenv('RESEND_API_KEY')

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = self.api_key or getattr(settings, 'RESEND_API_KEY', None) or os.getenv('RESEND_API_KEY')
        if not api_key:
            err_msg = "[ResendEmailBackend Error] RESEND_API_KEY environment variable or setting is missing."
            logger.error(err_msg)
            print(err_msg)
            if not self.fail_silently:
                raise ValueError(err_msg)
            return 0

        resend.api_key = api_key
        sent_count = 0

        for message in email_messages:
            try:
                from_email = message.from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'Box4 <info@box4homes.com>')
                if from_email == 'info@box4homes.com':
                    from_email = 'Box4 <info@box4homes.com>'

                recipients = list(message.to)
                
                params = {
                    "from": from_email,
                    "to": recipients,
                    "subject": message.subject,
                }

                # Extract HTML content if present in EmailMultiAlternatives
                html_content = None
                if hasattr(message, 'alternatives') and message.alternatives:
                    for content, mimetype in message.alternatives:
                        if mimetype == 'text/html':
                            html_content = content
                            break

                if html_content:
                    params["html"] = html_content
                    if message.body:
                        params["text"] = message.body
                elif message.body:
                    if "<html" in message.body.lower() or "<p>" in message.body.lower() or "<div" in message.body.lower():
                        params["html"] = message.body
                    else:
                        params["text"] = message.body

                if hasattr(message, 'reply_to') and message.reply_to:
                    params["reply_to"] = list(message.reply_to)
                if hasattr(message, 'cc') and message.cc:
                    params["cc"] = list(message.cc)
                if hasattr(message, 'bcc') and message.bcc:
                    params["bcc"] = list(message.bcc)

                response = resend.Emails.send(params)
                logger.info(f"[ResendEmailBackend] Successfully sent email to {recipients}. Resend ID: {response.get('id') if isinstance(response, dict) else response}")
                sent_count += 1
            except Exception as e:
                logger.error(f"[ResendEmailBackend Error] Failed to send email to {getattr(message, 'to', 'unknown')}: {e}", exc_info=True)
                print(f"[ResendEmailBackend Error] Failed to send email to {getattr(message, 'to', 'unknown')}: {e}")
                if not self.fail_silently:
                    raise e

        return sent_count
