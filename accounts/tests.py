from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from .models import EmailOTP
from profiles.models import BuyerProfile, AgentProfile, AdminProfile

User = get_user_model()

class AuthenticationTests(APITestCase):
    def setUp(self):
        self.register_url = reverse('auth_register')
        self.verify_otp_url = reverse('otp_verify')
        self.resend_otp_url = reverse('otp_resend')
        self.login_url = reverse('auth_login')
        self.google_url = reverse('google_auth')
        self.forgot_password_url = reverse('forgot_password')
        self.reset_password_url = reverse('reset_password')

    def test_register_buyer(self):
        data = {
            "email": "buyer@example.com",
            "password": "securepassword123",
            "full_name": "John Doe",
            "role": "buyer"
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['email'], "buyer@example.com")
        self.assertEqual(response.data['user']['role'], "buyer")
        self.assertFalse(response.data['user']['is_email_verified'])
        
        # Verify custom user creation
        user = User.objects.get(email="buyer@example.com")
        self.assertEqual(user.full_name, "John Doe")
        self.assertEqual(user.role, "buyer")
        self.assertFalse(user.is_email_verified)
        
        # Verify OTP record is generated
        otp = EmailOTP.objects.filter(user=user).first()
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp.otp_code), 4)

        # Verify Profile is automatically created by signals
        self.assertTrue(BuyerProfile.objects.filter(user=user).exists())

    def test_verify_otp_success(self):
        # Create unverified user
        user = User.objects.create_user(
            email="verify@example.com",
            username="verify@example.com",
            password="password",
            full_name="Jane Doe",
            role="agent"
        )
        otp = EmailOTP.objects.create(user=user)
        
        data = {
            "email": user.email,
            "otp_code": otp.otp_code
        }
        response = self.client.post(self.verify_otp_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", response.data)
        self.assertEqual(response.data['user']['role'], "agent")
        self.assertTrue(response.data['user']['is_email_verified'])
        
        # Check DB state
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_login_response_contains_role(self):
        user = User.objects.create_user(
            email="login@example.com",
            username="login@example.com",
            password="testpassword123",
            full_name="Test User",
            role="agent"
        )
        user.is_email_verified = True
        user.save()

        data = {
            "email": "login@example.com",
            "password": "testpassword123"
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data['role'], "agent")
        self.assertTrue(response.data['is_email_verified'])

    @patch('accounts.views.verify_google_token')
    def test_google_auth_new_user(self, mock_verify):
        mock_verify.return_value = {
            "email": "googlebuyer@example.com",
            "name": "Google User"
        }
        
        data = {
            "token": "mocked_id_token",
            "role": "buyer"
        }
        response = self.client.post(self.google_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_new_user'])
        self.assertEqual(response.data['user']['email'], "googlebuyer@example.com")
        self.assertEqual(response.data['user']['role'], "buyer")
        self.assertTrue(response.data['user']['is_email_verified']) # Google auth users are verified
        
        user = User.objects.get(email="googlebuyer@example.com")
        self.assertEqual(user.full_name, "Google User")
        self.assertTrue(user.is_email_verified)

    def test_forgot_password_generates_otp(self):
        user = User.objects.create_user(
            email="forgot@example.com",
            username="forgot@example.com",
            password="oldpassword",
            full_name="Forgot User"
        )
        response = self.client.post(self.forgot_password_url, {"email": user.email})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify password reset OTP was created
        otp = EmailOTP.objects.filter(user=user, otp_type='password_reset').first()
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp.otp_code), 4)

    def test_reset_password_success(self):
        user = User.objects.create_user(
            email="reset@example.com",
            username="reset@example.com",
            password="oldpassword",
            full_name="Reset User"
        )
        otp = EmailOTP.objects.create(user=user, otp_type='password_reset')
        
        data = {
            "email": user.email,
            "otp_code": otp.otp_code,
            "new_password": "brandnewpassword123"
        }
        response = self.client.post(self.reset_password_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check password is changed
        user.refresh_from_db()
        self.assertTrue(user.check_password("brandnewpassword123"))
        
        # Check OTP is marked as used
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)


class ProfileTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="profiletest@example.com",
            username="profiletest@example.com",
            password="password",
            full_name="Profile Tester",
            role="buyer"
        )
        self.user.is_email_verified = True
        self.user.save()
        
        # Get JWT tokens for auth
        response = self.client.post(reverse('auth_login'), {
            "email": "profiletest@example.com",
            "password": "password"
        })
        self.token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')
        
        self.profile_url = reverse('my_profile')
        self.onboard_url = reverse('profile_onboard')

    def test_get_profile(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['email'], self.user.email)

    def test_patch_profile_partial_update(self):
        data = {
            "phone_number": "+1234567890",
            "city": "San Francisco"
        }
        response = self.client.patch(self.profile_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['phone_number'], "+1234567890")
        self.assertEqual(response.data['city'], "San Francisco")
        
        # Check coordinates are still None (partial)
        self.assertIsNone(response.data['latitude'])

    def test_put_profile_forces_partial_update(self):
        # Standard PUT requests in DRF require all fields. But our view overrides it to allow partial updates.
        data = {
            "phone_number": "+9876543210",
        }
        response = self.client.put(self.profile_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['phone_number'], "+9876543210")
        # Ensure city is still "San Francisco" if not modified (in a regular PUT it would wipe city or fail validation)

    def test_onboarding_location_submission(self):
        data = {
            "phone_number": "+555666777",
            "latitude": "37.774900",
            "longitude": "-122.419400",
            "city": "San Francisco",
            "state": "CA",
            "country": "USA"
        }
        response = self.client.put(self.onboard_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['latitude']), 37.774900)
        self.assertEqual(float(response.data['longitude']), -122.419400)
        
        # Check DB State
        profile = BuyerProfile.objects.get(user=self.user)
        self.assertEqual(float(profile.latitude), 37.774900)
        self.assertEqual(float(profile.longitude), -122.419400)
