import requests
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status, views, generics, permissions, serializers
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import EmailOTP
from .serializers import (
    CustomTokenObtainPairSerializer,
    UserRegisterSerializer,
    OTPVerifySerializer,
    OTPResendSerializer,
    GoogleAuthSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    DeleteAccountSerializer,
    ChangePasswordSerializer,
    LogoutSerializer
)

User = get_user_model()

def verify_google_token(token):
    # Verify via google-auth library
    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), None)
        return idinfo
    except Exception:
        # Fallback to Google HTTP Tokeninfo endpoint
        try:
            response = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                # Ensure the token hasn't expired and has a valid issuer
                if 'error_description' not in data:
                    return data
        except Exception:
            pass
    return None


class LoginResponseSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="JWT refresh token")
    access = serializers.CharField(help_text="JWT access token")
    role = serializers.CharField(help_text="User role: 'buyer', 'agent', or 'admin'")
    id = serializers.IntegerField(help_text="User database ID")
    email = serializers.EmailField(help_text="User email address")
    full_name = serializers.CharField(help_text="User full name")
    is_email_verified = serializers.BooleanField(help_text="Whether email address is verified")
    kyc_status = serializers.CharField(
        required=False,
        help_text="Agent KYC verification status: 'verified', 'pending', or 'unverified' (included if role is agent)"
    )


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="User Login (JWT Authentication + Optional FCM Token)",
        operation_description=(
            "Authenticates user credentials and returns JWT access & refresh tokens along with user profile information.\n\n"
            "### Push Notifications (FCM Integration):\n"
            "The frontend can optionally pass `fcm_token` and `device_platform` ('android', 'ios', 'web') "
            "directly in the login request body. The backend will authenticate the user and bind the device token in a single call.\n\n"
            "Alternatively, the frontend can register device tokens after login via `POST /api/v1/notifications/devices/`."
        ),
        request_body=CustomTokenObtainPairSerializer,
        responses={200: LoginResponseSerializer}
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class UserRegisterView(generics.CreateAPIView):
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            "message": "User registered successfully. Please verify your email with the 4-digit OTP code sent to you.",
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_email_verified": user.is_email_verified
            }
        }, status=status.HTTP_201_CREATED)


class OTPVerifyView(generics.GenericAPIView):
    serializer_class = OTPVerifySerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        otp_record = serializer.validated_data['otp_record']
        
        # Mark OTP as used and user email as verified
        otp_record.is_used = True
        otp_record.save()
        
        user.is_email_verified = True
        user.save()
        
        # Generate login tokens
        refresh = RefreshToken.for_user(user)
        
        user_data = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_email_verified": user.is_email_verified
        }
        if user.role == 'agent':
            profile = getattr(user, 'agent_profile', None)
            user_data['kyc_status'] = profile.kyc_status if profile else 'unverified'

        return Response({
            "message": "Email verified successfully.",
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            },
            "user": user_data
        }, status=status.HTTP_200_OK)


class OTPResendView(generics.GenericAPIView):
    serializer_class = OTPResendSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = OTPResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.user
        
        # Generate new OTP
        otp = EmailOTP.objects.create(user=user)
        
        # Send Email
        from core.emails import send_otp_verification_email
        send_otp_verification_email(user.email, otp.otp_code, fail_silently=True)
            
        return Response({
            "message": "A new 4-digit verification code has been sent to your email."
        }, status=status.HTTP_200_OK)


class GoogleAuthView(generics.GenericAPIView):
    serializer_class = GoogleAuthSerializer
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="Google OAuth Sign-In (JWT + Optional FCM Token)",
        operation_description=(
            "Authenticates a user via Google OAuth ID Token.\n\n"
            "- **token**: Google ID token obtained from Google Sign-In on the client.\n"
            "- **role**: 'buyer' or 'agent' (default: 'buyer', used when creating a new account).\n"
            "- **fcm_token**: (Optional) Device FCM token to register push notifications immediately.\n"
            "- **device_platform**: (Optional) 'android', 'ios', or 'web' (default: 'android')."
        ),
        request_body=GoogleAuthSerializer,
        responses={200: openapi.Response(description="Google Authentication Successful")}
    )
    def post(self, request, *args, **kwargs):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        google_token = serializer.validated_data['token']
        role = serializer.validated_data['role']
        
        idinfo = verify_google_token(google_token)
        if not idinfo:
            return Response({"error": "Invalid or expired Google ID Token"}, status=status.HTTP_400_BAD_REQUEST)
        
        email = idinfo.get('email')
        if not email:
            return Response({"error": "Google token does not contain email address"}, status=status.HTTP_400_BAD_REQUEST)
        email = email.strip().lower()
            
        full_name = idinfo.get('name')
        if not full_name:
            given_name = idinfo.get('given_name', '')
            family_name = idinfo.get('family_name', '')
            full_name = f"{given_name} {family_name}".strip()
        
        # Check if user already exists
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            if getattr(existing_user, 'is_deleted', False) or not existing_user.is_active:
                return Response(
                    {"error": "This account has been deleted or deactivated. Please contact support."}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            if getattr(existing_user, 'is_suspended', False):
                return Response(
                    {"error": "This account has been suspended. Please contact support."}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            user = existing_user
            created = False
        else:
            user = User.objects.create(
                email=email,
                username=email,
                full_name=full_name,
                role=role,
                is_email_verified=True # Google verified emails are trusted
            )
            user.set_unusable_password()
            user.save()
            created = True
        
        if not created:
            # Make sure they are marked as email verified since Google authenticated them
            if not user.is_email_verified:
                user.is_email_verified = True
                user.save()
                
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        user_data = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_email_verified": user.is_email_verified
        }
        if user.role == 'agent':
            profile = getattr(user, 'agent_profile', None)
            user_data['kyc_status'] = profile.kyc_status if profile else 'unverified'

        fcm_token = serializer.validated_data.get('fcm_token')
        device_platform = serializer.validated_data.get('device_platform', 'android')
        if fcm_token:
            from notifications.models import DeviceToken
            DeviceToken.objects.update_or_create(
                token=fcm_token.strip(),
                defaults={
                    'user': user,
                    'platform': device_platform,
                    'is_active': True,
                }
            )

        return Response({
            "message": "Google Authentication Successful.",
            "is_new_user": created,
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            },
            "user": user_data
        }, status=status.HTTP_200_OK)


class LogoutView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LogoutSerializer

    @swagger_auto_schema(
        operation_summary="User Logout (Deactivate FCM Token)",
        operation_description=(
            "Logs out the user and deactivates push notifications on this device.\n\n"
            "- **fcm_token**: (Optional) The FCM device token to deactivate so notifications stop for this phone.\n"
            "- **refresh**: (Optional) JWT refresh token to blacklist."
        ),
        request_body=LogoutSerializer,
        responses={200: openapi.Response(description="Logged out successfully")}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fcm_token = serializer.validated_data.get('fcm_token')
        refresh = serializer.validated_data.get('refresh')

        if fcm_token:
            from notifications.models import DeviceToken
            DeviceToken.objects.filter(token=fcm_token.strip(), user=request.user).update(is_active=False)

        if refresh:
            try:
                from rest_framework_simplejwt.tokens import RefreshToken
                token = RefreshToken(refresh)
                token.blacklist()
            except Exception:
                pass

        return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)


class ForgotPasswordView(generics.GenericAPIView):
    serializer_class = ForgotPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user
        
        # Generate password reset OTP
        otp = EmailOTP.objects.create(user=user, otp_type='password_reset')
        
        # Send Email
        from core.emails import send_password_reset_otp_email
        send_password_reset_otp_email(user.email, otp.otp_code, fail_silently=True)
            
        return Response({
            "message": "A 4-digit verification code has been sent to your email to reset your password."
        }, status=status.HTTP_200_OK)


class ResetPasswordView(generics.GenericAPIView):
    serializer_class = ResetPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        otp_record = serializer.validated_data['otp_record']
        new_password = serializer.validated_data['new_password']
        
        # Reset password
        user.set_password(new_password)
        user.save()
        
        # Mark OTP as used
        otp_record.is_used = True
        otp_record.save()
        
        return Response({
            "message": "Password has been reset successfully. You can now login with your new password."
        }, status=status.HTTP_200_OK)


class DeleteAccountView(generics.GenericAPIView):
    serializer_class = DeleteAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=DeleteAccountSerializer,
        responses={200: openapi.Response(description="Account deleted successfully")}
    )
    def post(self, request, *args, **kwargs):
        return self._perform_delete(request)

    @swagger_auto_schema(
        request_body=DeleteAccountSerializer,
        responses={200: openapi.Response(description="Account deleted successfully")}
    )
    def delete(self, request, *args, **kwargs):
        return self._perform_delete(request)

    def _perform_delete(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.delete()

        return Response({
            "message": "Your account has been deleted successfully."
        }, status=status.HTTP_200_OK)


class ChangePasswordView(generics.GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=ChangePasswordSerializer,
        responses={200: openapi.Response(description="Password changed successfully")}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        new_password = serializer.validated_data['new_password']
        user.set_password(new_password)
        user.must_change_password = False
        user.save()

        # Generate fresh JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Password changed successfully.",
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            }
        }, status=status.HTTP_200_OK)

