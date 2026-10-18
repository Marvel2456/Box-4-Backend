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

    def test_register_with_uppercase_email_stores_lowercase(self):
        data = {
            "email": "Test.Buyer@Example.COM",
            "password": "securepassword123",
            "full_name": "Test Upper",
            "role": "buyer"
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['user']['email'], "test.buyer@example.com")

        # Verify DB entry is lowercase
        user = User.objects.get(email="test.buyer@example.com")
        self.assertEqual(user.email, "test.buyer@example.com")
        self.assertEqual(user.username, "test.buyer@example.com")

        # Attempt to register with uppercase again -> should fail with duplicate error
        dup_res = self.client.post(self.register_url, {
            "email": "TEST.BUYER@EXAMPLE.COM",
            "password": "anotherpassword123",
            "full_name": "Duplicate User",
            "role": "buyer"
        })
        self.assertEqual(dup_res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_with_uppercase_email(self):
        user = User.objects.create_user(
            email="caseuser@example.com",
            username="caseuser@example.com",
            password="testpassword123",
            full_name="Case User",
            role="buyer"
        )
        user.is_email_verified = True
        user.save()

        # Login with capitalized/uppercase email
        data = {
            "email": "CASEUSER@EXAMPLE.COM",
            "password": "testpassword123"
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertEqual(response.data['email'], "caseuser@example.com")

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
        self.assertEqual(response.data['kyc_status'], "unverified")

    def test_login_with_fcm_token_registers_device(self):
        user = User.objects.create_user(
            email="fcmuser@example.com",
            username="fcmuser@example.com",
            password="testpassword123",
            full_name="FCM User",
            role="buyer"
        )
        user.is_email_verified = True
        user.save()

        data = {
            "email": "fcmuser@example.com",
            "password": "testpassword123",
            "fcm_token": "fcm_token_from_mobile_12345",
            "device_platform": "android"
        }
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        from notifications.models import DeviceToken
        device = DeviceToken.objects.filter(token="fcm_token_from_mobile_12345").first()
        self.assertIsNotNone(device)
        self.assertEqual(device.user, user)
        self.assertEqual(device.platform, "android")
        self.assertTrue(device.is_active)

    def test_logout_deactivates_fcm_token(self):
        user = User.objects.create_user(
            email="logoutuser@example.com",
            username="logoutuser@example.com",
            password="testpassword123",
            full_name="Logout User",
            role="buyer"
        )
        user.is_email_verified = True
        user.save()

        from notifications.models import DeviceToken
        DeviceToken.objects.create(
            user=user,
            token="device_token_to_deactivate",
            platform="ios",
            is_active=True
        )

        self.client.force_authenticate(user=user)
        logout_url = reverse('auth_logout')
        response = self.client.post(logout_url, {"fcm_token": "device_token_to_deactivate"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        device = DeviceToken.objects.get(token="device_token_to_deactivate")
        self.assertFalse(device.is_active)

    def test_logout_blacklists_refresh_token(self):
        user = User.objects.create_user(
            email="blacklistuser@example.com",
            username="blacklistuser@example.com",
            password="testpassword123",
            full_name="Blacklist User",
            role="buyer"
        )
        user.is_email_verified = True
        user.save()

        # Login to obtain tokens
        login_res = self.client.post(self.login_url, {
            "email": "blacklistuser@example.com",
            "password": "testpassword123"
        })
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        refresh_token = login_res.data['refresh']
        access_token = login_res.data['access']

        # Confirm refresh token works before logout
        refresh_url = reverse('token_refresh')
        pre_logout_res = self.client.post(refresh_url, {"refresh": refresh_token})
        self.assertEqual(pre_logout_res.status_code, status.HTTP_200_OK)

        # Logout with refresh token
        logout_url = reverse('auth_logout')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        logout_res = self.client.post(logout_url, {"refresh": refresh_token})
        self.assertEqual(logout_res.status_code, status.HTTP_200_OK)

        # Confirm refresh token is now rejected after logout
        post_logout_res = self.client.post(refresh_url, {"refresh": refresh_token})
        self.assertEqual(post_logout_res.status_code, status.HTTP_401_UNAUTHORIZED)

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


class DeleteAccountTests(APITestCase):
    def setUp(self):
        self.delete_url = reverse('delete_account')
        self.login_url = reverse('auth_login')
        self.google_url = reverse('google_auth')
        self.forgot_password_url = reverse('forgot_password')

        # Create buyer user
        self.buyer = User.objects.create_user(
            email="deletebuyer@example.com",
            username="deletebuyer@example.com",
            password="securepassword123",
            full_name="Delete Buyer",
            role="buyer"
        )
        self.buyer.is_email_verified = True
        self.buyer.save()

        # Create agent user
        self.agent = User.objects.create_user(
            email="deleteagent@example.com",
            username="deleteagent@example.com",
            password="agentpassword123",
            full_name="Delete Agent",
            role="agent"
        )
        self.agent.is_email_verified = True
        self.agent.save()

    def test_unauthenticated_delete_account_fails(self):
        response = self.client.post(self.delete_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_buyer_hard_delete_account_success(self):
        buyer_id = self.buyer.id
        self.client.force_authenticate(user=self.buyer)
        response = self.client.post(self.delete_url, {"password": "securepassword123"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("deleted successfully", response.data['message'])

        self.assertFalse(User.objects.filter(id=buyer_id).exists())

        # Attempt login after deletion
        self.client.logout()
        login_resp = self.client.post(self.login_url, {
            "email": "deletebuyer@example.com",
            "password": "securepassword123"
        })
        self.assertEqual(login_resp.status_code, status.HTTP_401_UNAUTHORIZED)

        # Attempt forgot password after deletion
        forgot_resp = self.client.post(self.forgot_password_url, {
            "email": "deletebuyer@example.com"
        })
        self.assertEqual(forgot_resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('accounts.views.verify_google_token')
    def test_deleted_user_google_auth_blocked(self, mock_google_verify):
        buyer_id = self.buyer.id
        mock_google_verify.return_value = {
            'email': self.buyer.email,
            'name': 'Delete Buyer'
        }
        # First hard delete the buyer
        self.client.force_authenticate(user=self.buyer)
        self.client.post(self.delete_url, {"confirm": True})
        self.assertFalse(User.objects.filter(id=buyer_id).exists())

    def test_agent_hard_delete_cascades_listings(self):
        from agents.models import Category, Listing
        category = Category.objects.create(name="Apartment")
        listing = Listing.objects.create(
            agent=self.agent,
            title="Luxury Suite",
            category=category,
            price=50000.00,
            address="123 Ocean View",
            latitude=6.5244,
            longitude=3.3792,
            is_published=True,
            status='active'
        )
        agent_id = self.agent.id
        listing_id = listing.id

        self.client.force_authenticate(user=self.agent)
        response = self.client.delete(self.delete_url, {"confirm": True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertFalse(User.objects.filter(id=agent_id).exists())
        self.assertFalse(Listing.objects.filter(id=listing_id).exists())

    def test_delete_with_wrong_password_fails(self):
        self.client.force_authenticate(user=self.buyer)
        response = self.client.post(self.delete_url, {"password": "wrong_password_here"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

        self.assertTrue(User.objects.filter(id=self.buyer.id).exists())


class ChangePasswordTests(APITestCase):
    def setUp(self):
        self.change_password_url = reverse('change_password')
        self.login_url = reverse('auth_login')

        self.user = User.objects.create_user(
            email="changepass@example.com",
            username="changepass@example.com",
            password="originalpassword123",
            full_name="Password Changer",
            role="buyer"
        )
        self.user.is_email_verified = True
        self.user.must_change_password = True
        self.user.save()

    def test_unauthenticated_change_password_fails(self):
        response = self.client.post(self.change_password_url, {
            "old_password": "originalpassword123",
            "new_password": "brandnewpassword456"
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_success(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.change_password_url, {
            "old_password": "originalpassword123",
            "new_password": "brandnewpassword456",
            "confirm_password": "brandnewpassword456"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Password changed successfully", response.data['message'])
        self.assertIn("tokens", response.data)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("brandnewpassword456"))
        self.assertFalse(self.user.must_change_password)

        # Verify login with new password
        self.client.logout()
        login_resp = self.client.post(self.login_url, {
            "email": "changepass@example.com",
            "password": "brandnewpassword456"
        })
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)

    def test_change_password_wrong_old_password_fails(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.change_password_url, {
            "old_password": "wrongoldpassword",
            "new_password": "brandnewpassword456"
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("old_password", response.data)

    def test_change_password_same_password_fails(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.change_password_url, {
            "old_password": "originalpassword123",
            "new_password": "originalpassword123"
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)

    def test_change_password_mismatched_confirm_fails(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.change_password_url, {
            "old_password": "originalpassword123",
            "new_password": "brandnewpassword456",
            "confirm_password": "differentpassword789"
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("confirm_password", response.data)


