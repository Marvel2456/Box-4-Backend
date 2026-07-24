from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin
from .models import User, EmailOTP

# Unfold-styled User admin
class CustomUserAdmin(BaseUserAdmin, ModelAdmin):
    model = User
    list_display = ['email', 'username', 'role', 'is_email_verified', 'is_staff']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Roles & Status', {'fields': ('role', 'is_email_verified')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Custom Roles & Status', {'fields': ('role', 'is_email_verified')}),
    )

# Unfold-styled OTP admin
class EmailOTPAdmin(ModelAdmin):
    list_display = ['user', 'otp_code', 'otp_type', 'is_used', 'created_at', 'expires_at']
    list_filter = ['otp_type', 'is_used']
    search_fields = ['user__email', 'otp_code']

admin.site.register(User, CustomUserAdmin)
admin.site.register(EmailOTP, EmailOTPAdmin)
