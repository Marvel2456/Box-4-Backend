from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import BuyerProfile, AgentProfile, AdminProfile, Plan

class PlanAdmin(ModelAdmin):
    list_display = ['name', 'price', 'max_listings', 'max_boosted', 'max_featured']
    search_fields = ['name']


class BuyerProfileAdmin(ModelAdmin):
    list_display = ['user', 'phone_number', 'city', 'state', 'country', 'latitude', 'longitude']
    search_fields = ['user__email', 'phone_number', 'city', 'state', 'country']


class AgentProfileAdmin(ModelAdmin):
    list_display = ['user', 'plan', 'phone_number', 'agency_name', 'license_number', 'rating', 'city', 'state', 'country']
    list_filter = ['plan', 'rating']
    search_fields = ['user__email', 'phone_number', 'agency_name', 'license_number', 'city', 'state', 'country']


class AdminProfileAdmin(ModelAdmin):
    list_display = ['user', 'phone_number']
    search_fields = ['user__email', 'phone_number']


admin.site.register(Plan, PlanAdmin)
admin.site.register(BuyerProfile, BuyerProfileAdmin)
admin.site.register(AgentProfile, AgentProfileAdmin)
admin.site.register(AdminProfile, AdminProfileAdmin)
