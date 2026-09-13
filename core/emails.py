import os
import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)

def get_otp_html(otp_code, title="Email Verification", subtitle="Please use the verification code below to complete your authentication."):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 32px 16px;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0">
    <tr>
      <td align="center">
        <table width="100%" style="max-width: 500px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);" cellpadding="0" cellspacing="0">
          <tr>
            <td style="background-color: #0f172a; padding: 28px 32px; text-align: center;">
              <h1 style="color: #ffffff; font-size: 22px; font-weight: 800; letter-spacing: 2px; margin: 0; text-transform: uppercase;">Box-4 Real Estate</h1>
            </td>
          </tr>
          <tr>
            <td style="padding: 36px 32px;">
              <h2 style="color: #0f172a; font-size: 20px; font-weight: 700; margin: 0 0 12px 0; text-align: center;">{title}</h2>
              <p style="color: #64748b; font-size: 14px; line-height: 22px; margin: 0 0 28px 0; text-align: center;">{subtitle} This code will expire in <strong>10 minutes</strong>.</p>
              
              <div style="background-color: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 20px; text-align: center; margin-bottom: 28px;">
                <span style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 800; letter-spacing: 12px; color: #0284c7; display: inline-block; padding-left: 12px;">{otp_code}</span>
              </div>
              
              <p style="color: #94a3b8; font-size: 12px; line-height: 18px; margin: 0; text-align: center;">
                If you did not request this verification code, please ignore this email or contact support.
              </p>
            </td>
          </tr>
          <tr>
            <td style="background-color: #f8fafc; padding: 18px 32px; border-top: 1px solid #f1f5f9; text-align: center;">
              <p style="color: #94a3b8; font-size: 11px; margin: 0;">&copy; 2026 Box-4 Real Estate. All rights reserved.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_otp_verification_email(recipient_email, otp_code, fail_silently=False):
    """
    Send OTP verification email with HTML and text alternatives.
    """
    subject = "Your Box-4 Verification Code"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Box4 <info@box4homes.com>')
    if from_email == 'info@box4homes.com':
        from_email = 'Box4 <info@box4homes.com>'

    text_body = f"Your Box-4 email verification code is: {otp_code}\n\nThis code will expire in 10 minutes.\nIf you did not request this code, please ignore this email."
    html_body = get_otp_html(otp_code, title="Email Verification", subtitle="Please use the verification code below to verify your email address.")

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email,
        to=[recipient_email]
    )
    msg.attach_alternative(html_body, "text/html")
    
    try:
        sent = msg.send(fail_silently=fail_silently)
        logger.info(f"[send_otp_verification_email] Successfully sent OTP email to {recipient_email}")
        return sent
    except Exception as e:
        logger.error(f"[send_otp_verification_email Error] Failed to send OTP to {recipient_email}: {e}", exc_info=True)
        if not fail_silently:
            raise e
        return 0


def send_password_reset_otp_email(recipient_email, otp_code, fail_silently=False):
    """
    Send Password Reset OTP email with HTML and text alternatives.
    """
    subject = "Box-4 Password Reset Code"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Box4 <info@box4homes.com>')
    if from_email == 'info@box4homes.com':
        from_email = 'Box4 <info@box4homes.com>'

    text_body = f"Your Box-4 password reset code is: {otp_code}\n\nThis code will expire in 10 minutes.\nIf you did not request a password reset, please ignore this email."
    html_body = get_otp_html(otp_code, title="Password Reset Request", subtitle="We received a request to reset your password. Use the verification code below to proceed.")

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email,
        to=[recipient_email]
    )
    msg.attach_alternative(html_body, "text/html")
    
    try:
        sent = msg.send(fail_silently=fail_silently)
        logger.info(f"[send_password_reset_otp_email] Successfully sent password reset OTP to {recipient_email}")
        return sent
    except Exception as e:
        logger.error(f"[send_password_reset_otp_email Error] Failed to send reset OTP to {recipient_email}: {e}", exc_info=True)
        if not fail_silently:
            raise e
        return 0
