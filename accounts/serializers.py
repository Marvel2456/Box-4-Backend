from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import EmailOTP

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['email'] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['role'] = self.user.role
        data['id'] = self.user.id
        data['email'] = self.user.email
        data['full_name'] = self.user.full_name
        data['is_email_verified'] = self.user.is_email_verified
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
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        # Automatically set username to email if not provided
        if 'username' not in validated_data or not validated_data['username']:
            validated_data['username'] = validated_data['email']
            
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        
        # Generate and save OTP
        otp = EmailOTP.objects.create(user=user)
        
        # Send OTP code (will print to console/stdout in development)
        try:
            send_mail(
                subject="Email Verification Code",
                message=f"Your verification code is: {otp.otp_code}. It will expire in 10 minutes.",
                from_email="no-reply@realestate.com",
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception:
            # Silence email dispatch errors in dev environment
            pass
            
        return user


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=4, min_length=4)

    def validate(self, attrs):
        email = attrs.get('email')
        otp_code = attrs.get('otp_code')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")

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
        try:
            self.user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        return value


class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, default='buyer', required=False)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            self.user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp_code = serializers.CharField(max_length=4, min_length=4)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        email = attrs.get('email')
        otp_code = attrs.get('otp_code')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")

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

