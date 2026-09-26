from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin
from .models import User, EmailOTP

# Unfold-styled User admin
class CustomUserAdmin(ModelAdmin, BaseUserAdmin):
    model = User
    list_display = ['email', 'username', 'role', 'is_email_verified', 'is_deleted', 'is_suspended', 'is_staff']
    list_filter = ['role', 'is_email_verified', 'is_deleted', 'is_suspended', 'is_staff']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Roles & Status', {'fields': ('role', 'is_email_verified', 'is_suspended', 'is_deleted', 'deleted_at')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Custom Roles & Status', {'fields': ('role', 'is_email_verified', 'is_suspended', 'is_deleted', 'deleted_at')}),
    )

# Unfold-styled OTP admin
class EmailOTPAdmin(ModelAdmin):
    list_display = ['user', 'otp_code', 'otp_type', 'is_used', 'created_at', 'expires_at']
    list_filter = ['otp_type', 'is_used']
    search_fields = ['user__email', 'otp_code']

admin.site.register(User, CustomUserAdmin)
admin.site.register(EmailOTP, EmailOTPAdmin)
