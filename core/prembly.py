import os
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class PremblyService:
    """
    Prembly (Identitypass) KYC Integration Client.
    Provides automated verification for Nigerian NIN and CAC business registrations.
    """
    BASE_URL = "https://api.prembly.com"

    def __init__(self, secret_key=None, app_id=None, public_key=None, environment=None):
        self.secret_key = secret_key or getattr(settings, 'PREMBLY_SECRET_KEY', None) or os.getenv('PREMBLY_SECRET_KEY')
        self.public_key = public_key or getattr(settings, 'PREMBLY_PUBLIC_KEY', None) or os.getenv('PREMBLY_PUBLIC_KEY')
        self.app_id = app_id or getattr(settings, 'PREMBLY_APP_ID', None) or os.getenv('PREMBLY_APP_ID') or self.public_key
        self.environment = (environment or getattr(settings, 'PREMBLY_ENVIRONMENT', 'sandbox') or os.getenv('PREMBLY_ENVIRONMENT', 'sandbox')).lower()
        self.base_url = self.BASE_URL

    def _is_mock_mode(self):
        # Only mock if no key or dummy template placeholder is provided
        if not self.secret_key or str(self.secret_key).strip() in ["", "PREMBLY_SECRET_KEY", "your_prembly_secret_key_here"]:
            return True
        if any(placeholder in str(self.secret_key).lower() for placeholder in ['your_secret', 'mock_key', 'dummy_key']):
            return True
        return False

    def _get_headers(self):
        headers = {
            "x-api-key": self.secret_key or "",
            "app-id": self.app_id or self.public_key or "",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        if self.public_key:
            headers["public-key"] = self.public_key
        return headers

    def verify_nin(self, nin_number, first_name=None, last_name=None, dob=None):
        """
        Verify an agent's National Identity Number (NIN).
        Endpoint: /identitypass/verification/nin
        """
        nin_clean = str(nin_number).strip()
        if len(nin_clean) != 11 or not nin_clean.isdigit():
            return {
                "status": False,
                "verified": False,
                "message": "NIN must be an 11-digit number.",
                "data": None
            }

        if self._is_mock_mode():
            logger.info(f"[Prembly Mock] Simulating NIN verification for {nin_clean}")
            return {
                "status": True,
                "verified": True,
                "message": "NIN verified successfully (Sandbox Mock Mode)",
                "data": {
                    "nin": nin_clean,
                    "first_name": first_name or "Agent",
                    "last_name": last_name or "User",
                    "gender": "male",
                    "photo": None,
                    "phone_number": "08012345678",
                    "verification_status": "VERIFIED"
                }
            }

        url = f"{self.base_url}/identitypass/verification/nin"
        payload = {
            "number_nin": nin_clean,
            "number": nin_clean,
            "nin": nin_clean
        }
        if dob:
            payload["dob"] = dob

        try:
            response = requests.post(url, json=payload, headers=self._get_headers(), timeout=20)
            res_data = response.json() if response.content else {}

            verification_status = res_data.get('verification', {}).get('status', '').upper()
            is_success = response.status_code in [200, 201] and (
                res_data.get('status') is True or 
                res_data.get('response_code') in ['00', '01', 200] or
                verification_status == 'VERIFIED'
            )

            if is_success:
                inner_data = res_data.get('data') or res_data.get('nin_data') or res_data
                return {
                    "status": True,
                    "verified": True,
                    "message": res_data.get('detail') or res_data.get('message') or "NIN verified successfully.",
                    "data": inner_data
                }
            else:
                error_msg = res_data.get('detail') or res_data.get('message') or res_data.get('errors') or "NIN verification failed on Prembly."
                return {
                    "status": False,
                    "verified": False,
                    "message": str(error_msg),
                    "data": res_data
                }
        except requests.exceptions.RequestException as e:
            logger.error(f"[Prembly Request Error] NIN verification failed: {e}")
            return {
                "status": False,
                "verified": False,
                "message": f"Could not connect to Prembly identity server: {str(e)}",
                "data": None
            }

    def verify_cac(self, cac_number, company_type='RC', company_name=None):
        """
        Verify an agent's Corporate Affairs Commission (CAC) business/company registration.
        Endpoint: /identitypass/verification/cac
        company_type: 'RC' (Company) or 'BN' (Business Name) or 'IT' (Incorporated Trustees)
        """
        cac_clean = str(cac_number).strip().upper()
        if cac_clean.startswith('RC'):
            cac_clean = cac_clean.replace('RC', '').strip()
        elif cac_clean.startswith('BN'):
            cac_clean = cac_clean.replace('BN', '').strip()

        raw_type = str(company_type).strip().lower()
        if raw_type in ['co', 'rc', 'company']:
            comp_type_clean = 'RC'
        elif raw_type in ['bn', 'business_name', 'business name']:
            comp_type_clean = 'BN'
        elif raw_type in ['it', 'trustees']:
            comp_type_clean = 'IT'
        else:
            comp_type_clean = 'RC'

        if not cac_clean:
            return {
                "status": False,
                "verified": False,
                "message": "CAC registration number is required.",
                "data": None
            }

        if self._is_mock_mode():
            logger.info(f"[Prembly Mock] Simulating CAC verification for {cac_clean}")
            return {
                "status": True,
                "verified": True,
                "message": "CAC registration verified successfully (Sandbox Mock Mode)",
                "data": {
                    "rc_number": cac_clean,
                    "company_name": company_name or "Verified Real Estate Agency Ltd",
                    "company_type": comp_type_clean,
                    "registration_date": "2020-01-15",
                    "status": "ACTIVE",
                    "branch_address": "Lagos, Nigeria"
                }
            }

        url = f"{self.base_url}/identitypass/verification/cac"
        payload = {
            "rc_number": cac_clean,
            "company_type": comp_type_clean
        }
        if company_name:
            payload["company_name"] = company_name

        try:
            response = requests.post(url, json=payload, headers=self._get_headers(), timeout=20)
            res_data = response.json() if response.content else {}

            verification_status = res_data.get('verification', {}).get('status', '').upper()
            is_success = response.status_code in [200, 201] and (
                res_data.get('status') is True or 
                res_data.get('response_code') in ['00', '01', 200] or
                verification_status == 'VERIFIED'
            )

            if is_success:
                inner_data = res_data.get('data') or res_data.get('cac_data') or res_data
                return {
                    "status": True,
                    "verified": True,
                    "message": res_data.get('detail') or res_data.get('message') or "CAC verified successfully.",
                    "data": inner_data
                }
            else:
                error_msg = res_data.get('detail') or res_data.get('message') or res_data.get('errors') or "CAC verification failed on Prembly."
                return {
                    "status": False,
                    "verified": False,
                    "message": str(error_msg),
                    "data": res_data
                }
        except requests.exceptions.RequestException as e:
            logger.error(f"[Prembly Request Error] CAC verification failed: {e}")
            return {
                "status": False,
                "verified": False,
                "message": f"Could not connect to Prembly identity server: {str(e)}",
                "data": None
            }
