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
        username_field = self.username_field
        if username_field in attrs and isinstance(attrs[username_field], str):
            attrs[username_field] = attrs[username_field].strip().lower()
        if 'email' in attrs and isinstance(attrs['email'], str):
            attrs['email'] = attrs['email'].strip().lower()
        if 'username' in attrs and isinstance(attrs['username'], str):
            attrs['username'] = attrs['username'].strip().lower()

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
        return value


class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, default='buyer', required=False)


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        value = value.strip().lower()
        try:
            self.user = User.objects.get(email__iexact=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
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

