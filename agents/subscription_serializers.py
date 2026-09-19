from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from profiles.models import Plan, BoostPlan, AgentSubscription, ListingBoostPlacement
from agents.models import Listing

class AgentPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'description', 'price', 'billing_cycle',
            'max_boosted', 'max_featured', 'max_images_per_listing',
            'has_verified_badge', 'features', 'is_popular'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not data.get('features'):
            features = []
            if instance.max_boosted > 0:
                features.append(f"Up to {instance.max_boosted} active boosted listings")
            else:
                features.append("Unlimited active boosted listings")
            if instance.max_featured > 0:
                features.append(f"{instance.max_featured} free featured listings/mo")
            if instance.max_images_per_listing > 0:
                features.append(f"Up to {instance.max_images_per_listing} photos per listing")
            else:
                features.append("Unlimited photos per listing")
            if instance.has_verified_badge:
                features.append("Verified Agent Badge")
            data['features'] = features
        return data


class AgentBoostPlanSerializer(serializers.ModelSerializer):
    duration_text = serializers.SerializerMethodField()

    class Meta:
        model = BoostPlan
        fields = ['id', 'name', 'duration_days', 'duration_text', 'price', 'description', 'features']

    def get_duration_text(self, obj):
        return f"{obj.duration_days} Days"


class AgentSubscriptionUsageSerializer(serializers.Serializer):
    active_boosted_count = serializers.IntegerField()
    max_boosted = serializers.IntegerField()
    can_boost_more = serializers.BooleanField()
    
    featured_used_this_month = serializers.IntegerField()
    max_featured = serializers.IntegerField()
    can_feature_more = serializers.BooleanField()
    
    max_images_per_listing = serializers.IntegerField()
    has_verified_badge = serializers.BooleanField()


class AgentSubscriptionStatusSerializer(serializers.Serializer):
    has_active_subscription = serializers.BooleanField()
    status = serializers.CharField()
    plan = AgentPlanSerializer(allow_null=True)
    date_started = serializers.DateTimeField(allow_null=True)
    next_renewal = serializers.DateTimeField(allow_null=True)
    days_left = serializers.IntegerField()
    auto_renew = serializers.BooleanField()
    payment_method = serializers.CharField(allow_null=True)
    usage = AgentSubscriptionUsageSerializer()


class AgentSubscribeSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField(help_text="UUID of the subscription plan to purchase or switch to.")
    payment_method = serializers.CharField(required=False, default="card", help_text="Payment method e.g. 'card', 'bank_transfer', 'paystack'.")
    auto_renew = serializers.BooleanField(required=False, default=True)
    transaction_reference = serializers.CharField(required=False, allow_blank=True, default=None)

    def validate_plan_id(self, value):
        try:
            plan = Plan.objects.get(pk=value, is_active=True)
            return plan
        except Plan.DoesNotExist:
            raise serializers.ValidationError("Selected subscription plan was not found or is inactive.")


class AgentSubscriptionHistorySerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', default='Custom Plan')
    plan_price = serializers.DecimalField(source='plan.price', max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        model = AgentSubscription
        fields = [
            'id', 'plan', 'plan_name', 'plan_price', 'amount',
            'status', 'auto_renew', 'payment_method', 'transaction_reference',
            'date_started', 'next_renewal', 'created_at'
        ]


class ListingBoostRequestSerializer(serializers.Serializer):
    boost_plan_id = serializers.UUIDField(help_text="UUID of the boost plan/duration package to apply.")
    payment_method = serializers.CharField(required=False, default="card")
    payment_reference = serializers.CharField(required=False, allow_blank=True, default=None)

    def validate_boost_plan_id(self, value):
        try:
            boost_plan = BoostPlan.objects.get(pk=value, is_active=True)
            return boost_plan
        except BoostPlan.DoesNotExist:
            raise serializers.ValidationError("Selected boost plan was not found or is inactive.")


class ListingBoostPlacementSerializer(serializers.ModelSerializer):
    boost_plan_name = serializers.CharField(source='boost_plan.name', default='Custom Boost')

    class Meta:
        model = ListingBoostPlacement
        fields = [
            'id', 'listing', 'boost_plan', 'boost_plan_name', 'amount',
            'duration_days', 'date_started', 'date_expires', 'status',
            'payment_reference', 'created_at'
        ]
