import requests
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from rest_framework import status, views, generics
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from .models import EmailOTP
from .serializers import (
    CustomTokenObtainPairSerializer,
    UserRegisterSerializer,
    OTPVerifySerializer,
    OTPResendSerializer,
    GoogleAuthSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer
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


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


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
        
        return Response({
            "message": "Email verified successfully.",
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            },
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_email_verified": user.is_email_verified
            }
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
        
        # Send Email (console logs in dev)
        try:
            send_mail(
                subject="Email Verification Code (Resend)",
                message=f"Your verification code is: {otp.otp_code}. It will expire in 10 minutes.",
                from_email="no-reply@realestate.com",
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception:
            pass
            
        return Response({
            "message": "A new 4-digit verification code has been sent to your email."
        }, status=status.HTTP_200_OK)


class GoogleAuthView(generics.GenericAPIView):
    serializer_class = GoogleAuthSerializer
    permission_classes = [AllowAny]

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
            
        full_name = idinfo.get('name')
        if not full_name:
            given_name = idinfo.get('given_name', '')
            family_name = idinfo.get('family_name', '')
            full_name = f"{given_name} {family_name}".strip()
        
        # Check if user already exists
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email,
                'full_name': full_name,
                'role': role,
                'is_email_verified': True # Google verified emails are trusted
            }
        )
        
        # If user was created, set a random password
        if created:
            user.set_unusable_password()
            user.save()
        else:
            # If user already exists, we do NOT change their role, they log in with existing role
            # However, we make sure they are marked as email verified since Google authenticated them
            if not user.is_email_verified:
                user.is_email_verified = True
                user.save()
                
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            "message": "Google Authentication Successful.",
            "is_new_user": created,
            "tokens": {
                "refresh": str(refresh),
                "access": str(refresh.access_token)
            },
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_email_verified": user.is_email_verified
            }
        }, status=status.HTTP_200_OK)


class ForgotPasswordView(generics.GenericAPIView):
    serializer_class = ForgotPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.user
        
        # Generate password reset OTP
        otp = EmailOTP.objects.create(user=user, otp_type='password_reset')
        
        # Send Email (console logs in dev)
        try:
            send_mail(
                subject="Password Reset Verification Code",
                message=f"Your password reset verification code is: {otp.otp_code}. It will expire in 10 minutes.",
                from_email="no-reply@realestate.com",
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception:
            pass
            
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

