from rest_framework import generics, status, permissions
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from profiles.models import Plan, BoostPlan, AgentProfile, AgentSubscription, ListingBoostPlacement
from agents.models import Listing
from .subscription_serializers import (
    AgentPlanSerializer,
    AgentBoostPlanSerializer,
    AgentSubscriptionStatusSerializer,
    AgentSubscribeSerializer,
    AgentSubscriptionHistorySerializer,
)


class AgentPlanListView(generics.ListAPIView):
    """
    List all active subscription plans available for agents.
    """
    permission_classes = [permissions.AllowAny]
    queryset = Plan.objects.filter(is_active=True).order_by('price')
    serializer_class = AgentPlanSerializer
    pagination_class = None

    @swagger_auto_schema(
        operation_description="Get all active subscription plans available for agents with pricing and thresholds.",
        responses={200: AgentPlanSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AgentBoostPlanListView(generics.ListAPIView):
    """
    List all active Pay-As-You-Boost duration packages available for agents.
    """
    permission_classes = [permissions.AllowAny]
    queryset = BoostPlan.objects.filter(is_active=True).order_by('duration_days', 'price')
    serializer_class = AgentBoostPlanSerializer
    pagination_class = None

    @swagger_auto_schema(
        operation_description="Get all available Pay-As-You-Boost duration packages with pricing and duration in days.",
        responses={200: AgentBoostPlanSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AgentCurrentSubscriptionView(generics.GenericAPIView):
    """
    Get current Agent's subscription status, renewal info, and live usage counters.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AgentSubscriptionStatusSerializer

    @swagger_auto_schema(
        operation_description="Get current Agent active subscription details, days remaining, renewal date, and live quota usage counters.",
        responses={200: AgentSubscriptionStatusSerializer}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        profile = getattr(user, 'agent_profile', None)

        plan = profile.plan if profile else None
        latest_sub = AgentSubscription.objects.filter(agent=user, status='active').order_by('-created_at').first()

        # Calculate quotas & thresholds
        # 1. Active Boosted listings count (concurrent)
        active_boosted_count = Listing.objects.filter(agent=user, is_boosted=True).count()
        # Free default limit is 2 active boosted listings if no paid plan
        max_boosted = plan.max_boosted if plan else 2
        can_boost_more = (max_boosted == 0) or (active_boosted_count < max_boosted)

        # 2. Featured listings used in current billing cycle / month
        start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        featured_used_this_month = Listing.objects.filter(
            agent=user,
            is_featured=True,
            updated_at__gte=start_of_month
        ).count()
        max_featured = plan.max_featured if plan else 0
        can_feature_more = (max_featured == 0 and plan is not None) or (featured_used_this_month < max_featured)

        # 3. Media limits
        max_images = plan.max_images_per_listing if plan else 10
        has_verified_badge = plan.has_verified_badge if plan else False

        # Status & Renewal
        has_active_sub = bool(plan is not None and (latest_sub is None or latest_sub.status == 'active'))
        sub_status = latest_sub.status if latest_sub else ('active' if plan else 'free')
        date_started = latest_sub.date_started if latest_sub else None
        next_renewal = latest_sub.next_renewal if latest_sub else None

        days_left = 0
        if next_renewal:
            delta = next_renewal - timezone.now()
            days_left = max(0, delta.days)
        elif plan:
            days_left = 30

        usage_data = {
            "active_boosted_count": active_boosted_count,
            "max_boosted": max_boosted,
            "can_boost_more": can_boost_more,
            "featured_used_this_month": featured_used_this_month,
            "max_featured": max_featured,
            "can_feature_more": can_feature_more,
            "max_images_per_listing": max_images,
            "has_verified_badge": has_verified_badge,
        }

        response_data = {
            "has_active_subscription": has_active_sub,
            "status": sub_status,
            "plan": AgentPlanSerializer(plan).data if plan else None,
            "date_started": date_started,
            "next_renewal": next_renewal,
            "days_left": days_left,
            "auto_renew": latest_sub.auto_renew if latest_sub else True,
            "payment_method": latest_sub.payment_method if latest_sub else None,
            "usage": usage_data
        }

        return Response(response_data, status=status.HTTP_200_OK)


class AgentSubscribeView(generics.GenericAPIView):
    """
    Subscribe to a new plan or switch (upgrade/downgrade) an existing subscription plan.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AgentSubscribeSerializer

    @swagger_auto_schema(
        operation_description="Subscribe to a subscription plan or switch plans.",
        responses={200: "Subscribed successfully.", 400: "Invalid plan or request data."}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan = serializer.validated_data['plan_id']
        payment_method = serializer.validated_data.get('payment_method', 'card')
        auto_renew = serializer.validated_data.get('auto_renew', True)
        transaction_ref = serializer.validated_data.get('transaction_reference')

        user = request.user
        profile, _ = AgentProfile.objects.get_or_create(user=user)

        # Calculate renewal date based on billing cycle
        days_duration = 30
        if plan.billing_cycle == 'quarterly':
            days_duration = 90
        elif plan.billing_cycle == 'yearly':
            days_duration = 365

        renewal_date = timezone.now() + timedelta(days=days_duration)

        # Deactivate previous active subscriptions
        AgentSubscription.objects.filter(agent=user, status='active').update(status='cancelled')

        # Create new active subscription
        sub = AgentSubscription.objects.create(
            agent=user,
            plan=plan,
            amount=plan.price,
            next_renewal=renewal_date,
            status='active',
            auto_renew=auto_renew,
            payment_method=payment_method,
            transaction_reference=transaction_ref
        )

        # Update profile
        profile.plan = plan
        if plan.has_verified_badge:
            profile.is_verified = True
        profile.save()

        return Response({
            "message": f"Successfully subscribed to the '{plan.name}' plan!",
            "subscription": {
                "id": str(sub.id),
                "plan_name": plan.name,
                "price": float(plan.price),
                "billing_cycle": plan.billing_cycle,
                "date_started": sub.date_started,
                "next_renewal": sub.next_renewal,
                "status": sub.status,
                "auto_renew": sub.auto_renew
            }
        }, status=status.HTTP_200_OK)


class AgentCancelSubscriptionView(generics.GenericAPIView):
    """
    Cancel an active subscription / disable auto-renewal.
    """
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Cancel current active subscription or disable auto-renewal.",
        responses={200: "Subscription cancelled successfully."}
    )
    def post(self, request, *args, **kwargs):
        user = request.user
        active_sub = AgentSubscription.objects.filter(agent=user, status='active').first()

        if active_sub:
            active_sub.auto_renew = False
            active_sub.status = 'cancelled'
            active_sub.save()

        profile = getattr(user, 'agent_profile', None)
        if profile:
            profile.plan = None
            profile.save()

        return Response({
            "message": "Your subscription has been cancelled successfully. You are now on the Free tier."
        }, status=status.HTTP_200_OK)


class AgentSubscriptionHistoryView(generics.ListAPIView):
    """
    Get past subscription invoices and billing history.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AgentSubscriptionHistorySerializer

    def get_queryset(self):
        return AgentSubscription.objects.filter(agent=self.request.user).select_related('plan').order_by('-created_at')

    @swagger_auto_schema(
        operation_description="Get current Agent's billing history and past invoices.",
        responses={200: AgentSubscriptionHistorySerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
