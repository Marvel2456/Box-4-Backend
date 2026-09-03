from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import BuyerProfile, AgentProfile, AdminProfile, Plan, AgentKYC


class AgentKYCAdmin(ModelAdmin):
    list_display = ['agent_profile', 'status', 'nin_number', 'nin_verified', 'cac_number', 'cac_verified', 'attempts_count', 'verified_at', 'updated_at']
    list_filter = ['status', 'nin_verified', 'cac_verified']
    search_fields = ['agent_profile__user__email', 'nin_number', 'cac_number', 'agent_profile__agency_name']


class PlanAdmin(ModelAdmin):
    list_display = ['name', 'price', 'max_listings', 'max_boosted', 'max_featured']
    search_fields = ['name']


class BuyerProfileAdmin(ModelAdmin):
    list_display = ['user', 'phone_number', 'city', 'state', 'country', 'latitude', 'longitude']
    search_fields = ['user__email', 'phone_number', 'city', 'state', 'country']


class AgentProfileAdmin(ModelAdmin):
    list_display = ['user', 'plan', 'phone_number', 'agency_name', 'license_number', 'rating', 'kyc_status', 'city', 'state', 'country']
    list_filter = ['plan', 'rating']
    search_fields = ['user__email', 'phone_number', 'agency_name', 'license_number', 'city', 'state', 'country']


class AdminProfileAdmin(ModelAdmin):
    list_display = ['user', 'phone_number']
    search_fields = ['user__email', 'phone_number']


admin.site.register(Plan, PlanAdmin)
admin.site.register(BuyerProfile, BuyerProfileAdmin)
admin.site.register(AgentProfile, AgentProfileAdmin)
admin.site.register(AgentKYC, AgentKYCAdmin)
admin.site.register(AdminProfile, AdminProfileAdmin)

