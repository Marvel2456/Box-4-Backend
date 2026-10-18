from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import EmailOTP

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    fcm_token = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        write_only=True,
        help_text="Optional FCM device token for push notifications"
    )
    device_platform = serializers.ChoiceField(
        choices=[('android', 'Android'), ('ios', 'iOS'), ('web', 'Web')],
        default='android',
        required=False,
        write_only=True,
        help_text="Device platform (android, ios, or web)"
    )

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['email'] = user.email
        return token

    def validate(self, attrs):
        fcm_token = attrs.pop('fcm_token', None)
        device_platform = attrs.pop('device_platform', 'android')

        username_field = self.username_field
        if username_field in attrs and isinstance(attrs[username_field], str):
            attrs[username_field] = attrs[username_field].strip().lower()
        if 'email' in attrs and isinstance(attrs['email'], str):
            attrs['email'] = attrs['email'].strip().lower()
        if 'username' in attrs and isinstance(attrs['username'], str):
            attrs['username'] = attrs['username'].strip().lower()

        data = super().validate(attrs)
        
        if getattr(self.user, 'is_deleted', False) or not self.user.is_active:
            raise serializers.ValidationError("This account has been deleted or deactivated.")
            
        if getattr(self.user, 'is_suspended', False):
            raise serializers.ValidationError("This account has been suspended. Please contact support.")

        if fcm_token:
            from notifications.models import DeviceToken
            DeviceToken.objects.update_or_create(
                token=fcm_token.strip(),
                defaults={
                    'user': self.user,
                    'platform': device_platform,
                    'is_active': True,
                }
            )

        data['role'] = self.user.role
        data['id'] = self.user.id
        data['email'] = self.user.email
        data['full_name'] = self.user.full_name
        data['is_email_verified'] = self.user.is_email_verified
        if self.user.role == 'agent':
            profile = getattr(self.user, 'agent_profile', None)
            kyc_status = profile.kyc_status if profile else 'unverified'
            data['kyc_status'] = kyc_status
        return data


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'full_name', 'role')
        extra_kwargs = {
            'full_name': {'required': True},
        }

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError("Email is required.")
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        # Automatically lowercase email and username
        validated_data['email'] = validated_data['email'].strip().lower()
        if 'username' not in validated_data or not validated_data['username']:
            validated_data['username'] = validated_data['email']
        else:
            validated_data['username'] = validated_data['username'].strip().lower()
            
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        
        # Generate and save OTP
        otp = EmailOTP.objects.create(user=user)
        
        # Send OTP verification email
        from core.emails import send_otp_verification_email
        send_otp_verification_email(user.email, otp.otp_code, fail_silently=True)
            
        return user


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=4, min_length=4)

    def validate(self, attrs):
        email = attrs.get('email')
        if email:
            email = email.strip().lower()
            attrs['email'] = email
        otp_code = attrs.get('otp_code')

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")

        if getattr(user, 'is_deleted', False) or not user.is_active:
            raise serializers.ValidationError("This account has been deleted or deactivated.")

        otp_record = EmailOTP.objects.filter(
            user=user, 
            otp_code=otp_code, 
            is_used=False,
            otp_type='email_verification'
        ).order_by('-created_at').first()

        if not otp_record:
            raise serializers.ValidationError("Invalid verification code.")

        if otp_record.is_expired:
            raise serializers.ValidationError("This verification code has expired.")

        attrs['user'] = user
        attrs['otp_record'] = otp_record
        return attrs


class OTPResendSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        value = value.strip().lower()
        try:
            self.user = User.objects.get(email__iexact=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        if getattr(self.user, 'is_deleted', False) or not self.user.is_active:
            raise serializers.ValidationError("This account has been deleted or deactivated.")
        return value


class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, default='buyer', required=False)
    fcm_token = serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="Optional FCM device token for push notifications")
    device_platform = serializers.ChoiceField(
        choices=[('android', 'Android'), ('ios', 'iOS'), ('web', 'Web')],
        default='android',
        required=False,
        help_text="Device platform (android, ios, or web)"
    )


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, allow_blank=True, allow_null=True, help_text="Optional refresh token to blacklist")
    fcm_token = serializers.CharField(required=False, allow_blank=True, allow_null=True, help_text="Optional FCM device token to deactivate on logout")


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        value = value.strip().lower()
        try:
            self.user = User.objects.get(email__iexact=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        if getattr(self.user, 'is_deleted', False) or not self.user.is_active:
            raise serializers.ValidationError("This account has been deleted or deactivated.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=4, min_length=4)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        email = attrs.get('email')
        if email:
            email = email.strip().lower()
            attrs['email'] = email
        otp_code = attrs.get('otp_code')

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")

        if getattr(user, 'is_deleted', False) or not user.is_active:
            raise serializers.ValidationError("This account has been deleted or deactivated.")

        otp_record = EmailOTP.objects.filter(
            user=user, 
            otp_code=otp_code, 
            is_used=False,
            otp_type='password_reset'
        ).order_by('-created_at').first()

        if not otp_record:
            raise serializers.ValidationError("Invalid verification code.")

        if otp_record.is_expired:
            raise serializers.ValidationError("This verification code has expired.")

        attrs['user'] = user
        attrs['otp_record'] = otp_record
        return attrs


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(
        required=False, 
        allow_blank=True, 
        write_only=True, 
        help_text="User's current password (optional for social auth accounts)"
    )
    confirm = serializers.BooleanField(
        required=False, 
        default=True, 
        help_text="Explicit confirmation to soft delete the account"
    )

    def validate(self, attrs):
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            user = request.user
            password = attrs.get('password')
            if password and user.has_usable_password():
                if not user.check_password(password):
                    raise serializers.ValidationError({"password": "Incorrect password."})
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        help_text="User's current password"
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        min_length=8,
        help_text="New password (minimum 8 characters)"
    )
    confirm_password = serializers.CharField(
        required=False,
        write_only=True,
        help_text="Confirmation of new password"
    )

    def validate_old_password(self, value):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication credentials required.")
        if not request.user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        old_password = attrs.get('old_password')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')

        if old_password and new_password and old_password == new_password:
            raise serializers.ValidationError({"new_password": "New password cannot be the same as your current password."})

        if confirm_password and new_password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "New passwords do not match."})

        return attrs

