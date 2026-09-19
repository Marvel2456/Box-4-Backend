from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import (
    BuyerProfile, AgentProfile, AdminProfile, Plan, AgentKYC,
    BoostPlan, ListingBoostPlacement, FeaturedPlan, ListingFeature, AgentSubscription
)


class AgentKYCAdmin(ModelAdmin):
    list_display = ['agent_profile', 'status', 'nin_number', 'nin_verified', 'cac_number', 'cac_verified', 'attempts_count', 'verified_at', 'updated_at']
    list_filter = ['status', 'nin_verified', 'cac_verified']
    search_fields = ['agent_profile__user__email', 'nin_number', 'cac_number', 'agent_profile__agency_name']


class PlanAdmin(ModelAdmin):
    list_display = ['name', 'price', 'billing_cycle', 'max_boosted', 'max_featured', 'max_images_per_listing', 'has_verified_badge', 'is_active', 'is_popular']
    list_filter = ['is_active', 'is_popular', 'billing_cycle', 'has_verified_badge']
    search_fields = ['name', 'description']


class BoostPlanAdmin(ModelAdmin):
    list_display = ['name', 'duration_days', 'price', 'is_active', 'created_at']
    list_filter = ['is_active', 'duration_days']
    search_fields = ['name', 'description']


class FeaturedPlanAdmin(ModelAdmin):
    list_display = ['name', 'duration_days', 'price', 'is_active', 'created_at']
    list_filter = ['is_active', 'duration_days']
    search_fields = ['name']


class AgentSubscriptionAdmin(ModelAdmin):
    list_display = ['agent', 'plan', 'amount', 'status', 'auto_renew', 'payment_method', 'date_started', 'next_renewal']
    list_filter = ['status', 'auto_renew', 'payment_method', 'plan']
    search_fields = ['agent__email', 'agent__full_name', 'plan__name', 'transaction_reference']


class ListingBoostPlacementAdmin(ModelAdmin):
    list_display = ['listing', 'agent', 'boost_plan', 'amount', 'duration_days', 'status', 'date_started', 'date_expires', 'payment_reference']
    list_filter = ['status', 'duration_days', 'boost_plan']
    search_fields = ['listing__title', 'agent__email', 'agent__full_name', 'payment_reference']


class ListingFeatureAdmin(ModelAdmin):
    list_display = ['listing', 'featured_plan', 'amount', 'status', 'date_started', 'date_due']
    list_filter = ['status', 'featured_plan']
    search_fields = ['listing__title', 'listing__agent__email']


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
admin.site.register(BoostPlan, BoostPlanAdmin)
admin.site.register(FeaturedPlan, FeaturedPlanAdmin)
admin.site.register(AgentSubscription, AgentSubscriptionAdmin)
admin.site.register(ListingBoostPlacement, ListingBoostPlacementAdmin)
admin.site.register(ListingFeature, ListingFeatureAdmin)
admin.site.register(BuyerProfile, BuyerProfileAdmin)
admin.site.register(AgentProfile, AgentProfileAdmin)
admin.site.register(AgentKYC, AgentKYCAdmin)
admin.site.register(AdminProfile, AdminProfileAdmin)
