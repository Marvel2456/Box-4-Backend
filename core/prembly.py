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

    def __init__(self, secret_key=None, app_id=None, environment=None):
        self.secret_key = secret_key or getattr(settings, 'PREMBLY_SECRET_KEY', None) or os.getenv('PREMBLY_SECRET_KEY')
        self.app_id = app_id or getattr(settings, 'PREMBLY_APP_ID', None) or os.getenv('PREMBLY_APP_ID')
        self.environment = (environment or getattr(settings, 'PREMBLY_ENVIRONMENT', 'sandbox') or os.getenv('PREMBLY_ENVIRONMENT', 'sandbox')).lower()
        self.base_url = self.BASE_URL

    def _is_mock_mode(self):
        if not self.secret_key or str(self.secret_key).strip() == "" or str(self.secret_key) == "PREMBLY_SECRET_KEY":
            return True
        if any(placeholder in str(self.secret_key).lower() for placeholder in ['your_', 'test_', 'mock', 'placeholder', 'dummy', 'prembly_secret_key']):
            return True
        return False

    def _get_headers(self):
        return {
            "x-api-key": self.secret_key or "",
            "app-id": self.app_id or "",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

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

        # Mock fallback for development/sandbox if live credentials are not set
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
            "number": nin_clean,
            "nin": nin_clean
        }
        if dob:
            payload["dob"] = dob

        try:
            response = requests.post(url, json=payload, headers=self._get_headers(), timeout=20)
            res_data = response.json() if response.content else {}

            is_success = response.status_code in [200, 201] and (
                res_data.get('status') is True or res_data.get('response_code') in ['00', '01', 200]
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
                error_msg = res_data.get('detail') or res_data.get('message') or "NIN verification failed on Prembly."
                return {
                    "status": False,
                    "verified": False,
                    "message": error_msg,
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

    def verify_cac(self, cac_number, company_type='co', company_name=None):
        """
        Verify an agent's Corporate Affairs Commission (CAC) business/company registration.
        Endpoint: /identitypass/verification/cac
        company_type: 'co' (RC Company) or 'bn' (Business Name) or 'it' (Incorporated Trustees)
        """
        cac_clean = str(cac_number).strip()
        comp_type_clean = str(company_type).strip().lower()

        if not cac_clean:
            return {
                "status": False,
                "verified": False,
                "message": "CAC registration number is required.",
                "data": None
            }

        # Mock fallback for development/sandbox if live credentials are not set
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

            is_success = response.status_code in [200, 201] and (
                res_data.get('status') is True or res_data.get('response_code') in ['00', '01', 200]
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
                error_msg = res_data.get('detail') or res_data.get('message') or "CAC verification failed on Prembly."
                return {
                    "status": False,
                    "verified": False,
                    "message": error_msg,
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
