import hmac
import hashlib
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class PaystackService:
    def __init__(self, secret_key=None, public_key=None, api_url=None):
        self.secret_key = secret_key or getattr(settings, 'PAYSTACK_SECRET_KEY', '')
        self.public_key = public_key or getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')
        self.api_url = (api_url or getattr(settings, 'PAYSTACK_API_URL', 'https://api.paystack.co')).rstrip('/')

    @property
    def is_configured(self):
        return bool(self.secret_key and self.secret_key.strip())

    def _get_headers(self):
        return {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def initialize_payment(self, email, amount, reference, callback_url=None, metadata=None, currency='NGN', channels=None):
        """
        Initialize a Paystack transaction.
        Amount is in Naira (or currency unit) and converted to kobo (integer) for Paystack API.
        """
        amount_kobo = int(round(float(amount) * 100))

        payload = {
            'email': email,
            'amount': amount_kobo,
            'reference': reference,
            'currency': currency,
        }

        if callback_url:
            payload['callback_url'] = callback_url
        if metadata:
            payload['metadata'] = metadata
        if channels:
            payload['channels'] = channels

        if not self.is_configured:
            logger.warning("PAYSTACK_SECRET_KEY is not configured in settings. Returning mock initialization.")
            return {
                'status': True,
                'message': 'Paystack mock initialization (configure PAYSTACK_SECRET_KEY for live transactions)',
                'data': {
                    'authorization_url': f"https://checkout.paystack.com/{reference}",
                    'access_code': f"mock_access_{reference}",
                    'reference': reference,
                }
            }

        url = f"{self.api_url}/transaction/initialize"
        try:
            response = requests.post(url, headers=self._get_headers(), json=payload, timeout=30)
            data = response.json()
            if response.status_code == 200 and data.get('status'):
                return data
            else:
                error_msg = data.get('message', 'Failed to initialize Paystack payment')
                logger.error(f"Paystack initialize error: {error_msg} | Status: {response.status_code} | Body: {data}")
                return {
                    'status': False,
                    'message': error_msg,
                    'data': data.get('data')
                }
        except requests.RequestException as e:
            logger.exception(f"Paystack HTTP request failed during initialization: {str(e)}")
            return {
                'status': False,
                'message': f"Network error communicating with Paystack: {str(e)}",
                'data': None
            }

    def verify_payment(self, reference):
        """
        Verify a transaction reference with Paystack API.
        """
        if not self.is_configured:
            logger.warning("PAYSTACK_SECRET_KEY is not configured in settings. Returning mock verification.")
            return {
                'status': True,
                'message': 'Mock verification successful (configure PAYSTACK_SECRET_KEY for live transactions)',
                'data': {
                    'status': 'success',
                    'reference': reference,
                    'amount': 0,
                    'gateway_response': 'Successful (Mock)',
                    'channel': 'card',
                    'currency': 'NGN'
                }
            }

        url = f"{self.api_url}/transaction/verify/{reference}"
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            data = response.json()
            if response.status_code == 200 and data.get('status'):
                return data
            else:
                error_msg = data.get('message', 'Failed to verify Paystack payment')
                logger.error(f"Paystack verify error: {error_msg} | Status: {response.status_code} | Body: {data}")
                return {
                    'status': False,
                    'message': error_msg,
                    'data': data.get('data')
                }
        except requests.RequestException as e:
            logger.exception(f"Paystack HTTP request failed during verification: {str(e)}")
            return {
                'status': False,
                'message': f"Network error communicating with Paystack: {str(e)}",
                'data': None
            }

    def verify_webhook_signature(self, payload_bytes, signature_header):
        """
        Verify HMAC SHA512 signature from Paystack webhook.
        """
        if not self.is_configured or not signature_header:
            return False

        computed_signature = hmac.new(
            self.secret_key.encode('utf-8'),
            payload_bytes,
            hashlib.sha512
        ).hexdigest()

        return hmac.compare_digest(computed_signature, signature_header)


# Singleton instance for general use
paystack_service = PaystackService()
