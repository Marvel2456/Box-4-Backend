from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import PlatformPolicy


@admin.register(PlatformPolicy)
class PlatformPolicyAdmin(ModelAdmin):
    list_display = ('id', 'updated_at', 'updated_by')
    readonly_fields = ('created_at', 'updated_at')
