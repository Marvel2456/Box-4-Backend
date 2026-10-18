from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    CustomTokenObtainPairView,
    UserRegisterView,
    OTPVerifyView,
    OTPResendView,
    GoogleAuthView,
    ForgotPasswordView,
    ResetPasswordView,
    DeleteAccountView,
    ChangePasswordView,
    LogoutView
)

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(), name='auth_login'),
    path('logout/', LogoutView.as_view(), name='auth_logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('register/', UserRegisterView.as_view(), name='auth_register'),
    path('verify-otp/', OTPVerifyView.as_view(), name='otp_verify'),
    path('resend-otp/', OTPResendView.as_view(), name='otp_resend'),
    path('google/', GoogleAuthView.as_view(), name='google_auth'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('delete-account/', DeleteAccountView.as_view(), name='delete_account'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
]
