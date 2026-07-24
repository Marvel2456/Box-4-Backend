from django.db import models
import uuid
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta
import random

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ROLE_CHOICES = (
        ('buyer', 'Buyer'),
        ('agent', 'Agent'),
        ('admin', 'Admin'),
        ('moderator', 'Moderator'),
    )
    
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='buyer')
    is_email_verified = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    is_suspended = models.BooleanField(default=False)
    
    # Use email as the username field
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return f"{self.email} ({self.role})"


class EmailOTP(models.Model):
    OTP_TYPE_CHOICES = (
        ('email_verification', 'Email Verification'),
        ('password_reset', 'Password Reset'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    otp_code = models.CharField(max_length=4)
    otp_type = models.CharField(max_length=20, choices=OTP_TYPE_CHOICES, default='email_verification')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.otp_code:
            self.otp_code = f"{random.randint(1000, 9999)}"
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"OTP {self.otp_code} ({self.otp_type}) for {self.user.email}"

