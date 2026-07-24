from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from agents.serializers import ListingSerializer
from profiles.models import Plan, FeaturedPlan, ListingFeature, AgentSubscription

User = get_user_model()

class AdminRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'password')

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['email'],
            password=validated_data['password'],
            full_name=validated_data.get('full_name', ''),
            role='admin',
            is_staff=True,
            is_email_verified=True
        )
        return user


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = authenticate(request=self.context.get('request'), username=email, password=password)
            if not user:
                # Fallback check if username parameter was passed
                user_obj = User.objects.filter(email=email).first()
                if user_obj and user_obj.check_password(password):
                    user = user_obj

            if not user:
                raise serializers.ValidationError("Invalid email or password.")

            if user.role != 'admin' and not user.is_staff and not user.is_superuser:
                raise serializers.ValidationError("Access denied. User is not an administrator.")

            if user.is_suspended:
                raise serializers.ValidationError("Account is suspended. Please contact support.")

            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError("Must include 'email' and 'password'.")


class AdminInviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=255)
    phone_number = serializers.CharField(max_length=20)
    role = serializers.ChoiceField(choices=[('admin', 'Admin'), ('moderator', 'Moderator')], default='admin')

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email address already exists.")
        return value


class AdminChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current/temporary password is incorrect.")
        return value


class OverviewListingItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    category = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField(source='title')
    photos_count = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    agent_name = serializers.CharField(source='agent.full_name', default=None)
    status = serializers.CharField()
    is_boosted = serializers.BooleanField()
    is_featured = serializers.BooleanField()
    created_at = serializers.DateTimeField()

    def get_photos_count(self, obj):
        return obj.images.count()

    def get_cover_photo(self, obj):
        request = self.context.get('request')
        cover = obj.images.filter(is_cover=True).first() or obj.images.first()
        if cover and cover.image:
            if request:
                return request.build_absolute_uri(cover.image.url)
            return cover.image.url
        return None


class StatItemWithWeekSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    added_this_week = serializers.IntegerField()

class ActiveListingsStatSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    percentage_of_total = serializers.FloatField()

class StatItemWithMonthSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    added_this_month = serializers.IntegerField()

class RevenueAssetsStatSerializer(serializers.Serializer):
    amount = serializers.FloatField()
    vs_last_month_percentage = serializers.FloatField()

class StatItemWithNoteSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    note = serializers.CharField()

class OverviewStatsSerializer(serializers.Serializer):
    total_properties = StatItemWithWeekSerializer()
    active_listings = ActiveListingsStatSerializer()
    agents = StatItemWithMonthSerializer()
    registered_users = StatItemWithMonthSerializer()
    revenue_assets = RevenueAssetsStatSerializer()
    reported_listings = StatItemWithNoteSerializer()
    pending_approvals = StatItemWithNoteSerializer()

class ChartDataItemSerializer(serializers.Serializer):
    day = serializers.CharField()
    count = serializers.IntegerField()

class ListingsAddedLast30DaysSerializer(serializers.Serializer):
    total_added = serializers.IntegerField()
    vs_last_month_percentage = serializers.FloatField()
    chart_data = ChartDataItemSerializer(many=True)

class OverviewDashboardResponseSerializer(serializers.Serializer):
    overview = OverviewStatsSerializer()
    listings_added_last_30_days = ListingsAddedLast30DaysSerializer()
    listings_by_type = serializers.DictField(child=serializers.IntegerField())
    recent_listings = OverviewListingItemSerializer(many=True)
    pending_approvals = OverviewListingItemSerializer(many=True)


class AdminPropertyDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    category = serializers.CharField()
    price = serializers.DecimalField(max_digits=12, decimal_places=2)
    address = serializers.CharField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    bedrooms = serializers.IntegerField()
    bathrooms = serializers.IntegerField()
    balconies = serializers.IntegerField()
    total_rooms = serializers.IntegerField()
    facilities = serializers.ListField(child=serializers.CharField())
    status = serializers.CharField()
    is_published = serializers.BooleanField()
    is_boosted = serializers.BooleanField()
    is_featured = serializers.BooleanField()
    is_reported = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    
    # Agent details
    agent_id = serializers.UUIDField(source='agent.id')
    agent_name = serializers.CharField(source='agent.full_name', default=None)
    agent_email = serializers.CharField(source='agent.email')
    agent_status = serializers.SerializerMethodField()
    
    # Photos
    images_count = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()

    def get_agent_status(self, obj):
        if obj.agent and obj.agent.is_email_verified:
            return "Verified"
        return "Unverified"

    def get_images_count(self, obj):
        return obj.images.count()

    def get_cover_photo(self, obj):
        request = self.context.get('request')
        cover = obj.images.filter(is_cover=True).first() or obj.images.first()
        if cover and cover.image:
            if request:
                return request.build_absolute_uri(cover.image.url)
            return cover.image.url
        return None

    def get_images(self, obj):
        request = self.context.get('request')
        photos = []
        for img in obj.images.all():
            if img.image:
                url = request.build_absolute_uri(img.image.url) if request else img.image.url
                photos.append({
                    "id": str(img.id),
                    "url": url,
                    "is_cover": img.is_cover
                })
        return photos


class BulkApproveSerializer(serializers.Serializer):
    property_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        help_text="Optional list of property IDs to bulk approve. If omitted, approves all pending properties."
    )


# Explicit List Response Schemas with header_stats for Swagger UI

class AllPropertiesHeaderStatsSerializer(serializers.Serializer):
    all_count = serializers.IntegerField()
    active_approved_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    featured_count = serializers.IntegerField()
    sold_count = serializers.IntegerField()

class AllPropertiesResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    header_stats = AllPropertiesHeaderStatsSerializer()
    results = AdminPropertyDetailSerializer(many=True)


class AwaitingReviewStatSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    oldest_note = serializers.CharField()

class ApprovedTodayStatSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    avg_review_note = serializers.CharField()

class RejectedTodayStatSerializer(serializers.Serializer):
    count = serializers.IntegerField()

class PendingPropertiesHeaderStatsSerializer(serializers.Serializer):
    awaiting_review = AwaitingReviewStatSerializer()
    approved_today = ApprovedTodayStatSerializer()
    rejected_today = RejectedTodayStatSerializer()

class PendingPropertiesResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    header_stats = PendingPropertiesHeaderStatsSerializer()
    results = AdminPropertyDetailSerializer(many=True)


class CurrentlyFeaturedStatSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    note = serializers.CharField()

class RevenueThisMonthStatSerializer(serializers.Serializer):
    amount = serializers.FloatField()
    vs_last_month_percentage = serializers.FloatField()

class ExpiringThisWeekStatSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    note = serializers.CharField()

class FeaturedPropertiesHeaderStatsSerializer(serializers.Serializer):
    currently_featured = CurrentlyFeaturedStatSerializer()
    revenue_this_month = RevenueThisMonthStatSerializer()
    expiring_this_week = ExpiringThisWeekStatSerializer()

class FeaturedPropertiesResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    header_stats = FeaturedPropertiesHeaderStatsSerializer()
    results = AdminPropertyDetailSerializer(many=True)


class SoldPropertiesHeaderStatsSerializer(serializers.Serializer):
    sold_count = serializers.IntegerField()

class SoldPropertiesResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    header_stats = SoldPropertiesHeaderStatsSerializer()
    results = AdminPropertyDetailSerializer(many=True)


# User Management Serializers & Response Schemas

class AdminAgentItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    email = serializers.EmailField()
    phone_number = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()
    listings_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    joined = serializers.SerializerMethodField()
    is_verified = serializers.SerializerMethodField()
    is_suspended = serializers.BooleanField()
    created_at = serializers.DateTimeField(source='date_joined')

    def get_phone_number(self, obj):
        if hasattr(obj, 'agent_profile') and obj.agent_profile and obj.agent_profile.phone_number:
            return obj.agent_profile.phone_number
        return getattr(obj, 'phone', None)

    def get_profile_picture(self, obj):
        request = self.context.get('request')
        pic = None
        if hasattr(obj, 'agent_profile') and obj.agent_profile and obj.agent_profile.profile_picture:
            pic = obj.agent_profile.profile_picture
        elif getattr(obj, 'profile_picture', None):
            pic = obj.profile_picture

        if pic and hasattr(pic, 'url'):
            if request:
                return request.build_absolute_uri(pic.url)
            return pic.url
        return None

    def get_listings_count(self, obj):
        return obj.listings.count()

    def get_status(self, obj):
        if obj.is_suspended:
            return "Suspended"
        if hasattr(obj, 'agent_profile') and obj.agent_profile and obj.agent_profile.is_verified:
            return "Verified"
        return "Unverified"

    def get_city(self, obj):
        if hasattr(obj, 'agent_profile') and obj.agent_profile and obj.agent_profile.city:
            return obj.agent_profile.city
        return "Lagos"

    def get_joined(self, obj):
        return obj.date_joined.strftime("%b %d")

    def get_is_verified(self, obj):
        if hasattr(obj, 'agent_profile') and obj.agent_profile:
            return obj.agent_profile.is_verified
        return False


class AgentsHeaderStatsSerializer(serializers.Serializer):
    total_agents = serializers.IntegerField()
    verified_agents = serializers.IntegerField()
    pending_verified = serializers.IntegerField()
    suspended_realtors = serializers.IntegerField()

class AgentsResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    header_stats = AgentsHeaderStatsSerializer()
    results = AdminAgentItemSerializer(many=True)


class AdminBuyerItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    full_name = serializers.CharField()
    email = serializers.EmailField()
    phone_number = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    joined = serializers.SerializerMethodField()
    saves_count = serializers.SerializerMethodField()
    inquiries_count = serializers.SerializerMethodField()
    is_suspended = serializers.BooleanField()
    created_at = serializers.DateTimeField(source='date_joined')

    def get_phone_number(self, obj):
        if hasattr(obj, 'buyer_profile') and obj.buyer_profile and obj.buyer_profile.phone_number:
            return obj.buyer_profile.phone_number
        return getattr(obj, 'phone', None)

    def get_profile_picture(self, obj):
        request = self.context.get('request')
        pic = None
        if hasattr(obj, 'buyer_profile') and obj.buyer_profile and obj.buyer_profile.profile_picture:
            pic = obj.buyer_profile.profile_picture
        elif getattr(obj, 'profile_picture', None):
            pic = obj.profile_picture

        if pic and hasattr(pic, 'url'):
            if request:
                return request.build_absolute_uri(pic.url)
            return pic.url
        return None

    def get_status(self, obj):
        if obj.is_suspended:
            return "Suspended"
        if obj.is_email_verified:
            return "Verified"
        return "Unverified"

    def get_city(self, obj):
        if hasattr(obj, 'buyer_profile') and obj.buyer_profile and obj.buyer_profile.city:
            return obj.buyer_profile.city
        return "Lagos"

    def get_joined(self, obj):
        return obj.date_joined.strftime("%b %d")

    def get_saves_count(self, obj):
        from buyers.models import SavedListing
        return SavedListing.objects.filter(buyer=obj).count()

    def get_inquiries_count(self, obj):
        from chat.models import Message
        return Message.objects.filter(sender=obj).count()


class TotalUsersStatSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    note = serializers.CharField()

class ActiveThisWeekStatSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    note = serializers.CharField()

class SuspendedAccountsStatSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    note = serializers.CharField()

class BuyersHeaderStatsSerializer(serializers.Serializer):
    total_users = TotalUsersStatSerializer()
    active_this_week = ActiveThisWeekStatSerializer()
    suspended_accounts = SuspendedAccountsStatSerializer()

class BuyersResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    header_stats = BuyersHeaderStatsSerializer()
    results = AdminBuyerItemSerializer(many=True)


class VerificationQueueHeaderStatsSerializer(serializers.Serializer):
    pending_verifications = serializers.IntegerField()
    approved_today = serializers.IntegerField()
    rejected_today = serializers.IntegerField()

class VerificationQueueResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    header_stats = VerificationQueueHeaderStatsSerializer()
    results = AdminAgentItemSerializer(many=True)


class SuspendedUsersHeaderStatsSerializer(serializers.Serializer):
    total_suspended = serializers.IntegerField()
    suspended_agents = serializers.IntegerField()
    suspended_buyers = serializers.IntegerField()

class SuspendedUsersResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    header_stats = SuspendedUsersHeaderStatsSerializer()
    results = AdminAgentItemSerializer(many=True)


# Reports & Moderation Serializers & Response Schemas

class AdminReportItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    listing_id = serializers.UUIDField(source='listing.id', default=None)
    listing_title = serializers.CharField(source='listing.title', default=None)
    target_id = serializers.SerializerMethodField()
    report_type = serializers.CharField()
    reason = serializers.CharField()
    description = serializers.CharField(default="")
    reporter = serializers.CharField(source='reporter.full_name', default="Anonymous")
    reporter_email = serializers.CharField(source='reporter.email', default=None)
    reported_user_name = serializers.CharField(source='reported_user.full_name', default=None)
    date = serializers.SerializerMethodField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()

    def get_target_id(self, obj):
        if obj.listing:
            short_id = str(obj.listing.id).replace('-', '').upper()[:6]
            return f"#{short_id}"
        elif obj.reported_user:
            short_id = str(obj.reported_user.id).replace('-', '').upper()[:6]
            return f"#{short_id}"
        short_id = str(obj.id).replace('-', '').upper()[:6]
        return f"#{short_id}"

    def get_date(self, obj):
        return obj.created_at.strftime("%b %d")


class ReportsHeaderStatsSerializer(serializers.Serializer):
    reported_listings = serializers.IntegerField()
    reported_users = serializers.IntegerField()
    auto_fraud_flags = serializers.IntegerField()
    resolved_this_week = serializers.IntegerField()


class ReportsModerationResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    header_stats = ReportsHeaderStatsSerializer()
    results = AdminReportItemSerializer(many=True)


# Finance Serializers & Response Schemas

class PlanManagementSerializer(serializers.ModelSerializer):
    subscribers_count = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = ['id', 'name', 'price', 'max_listings', 'max_boosted', 'max_featured', 'subscribers_count', 'features', 'created_at']

    def get_subscribers_count(self, obj):
        return obj.agent_profiles.count()

    def get_features(self, obj):
        listings_str = "Unlimited listings" if obj.max_listings == 0 else f"Up to {obj.max_listings} listings"
        res = [listings_str]
        if obj.max_featured > 0:
            res.append(f"{obj.max_featured} free featured/month")
        else:
            res.append("Basic analytics")
        res.append("Priority support" if obj.price > 20 else "Email support")
        return res


class FeaturedPlanManagementSerializer(serializers.ModelSerializer):
    active_count = serializers.SerializerMethodField()

    class Meta:
        model = FeaturedPlan
        fields = ['id', 'name', 'duration_days', 'price', 'features', 'active_count', 'created_at']

    def get_active_count(self, obj):
        return obj.listing_features.filter(status='active').count()


class FinanceHeaderStatsSerializer(serializers.Serializer):
    revenue_this_month = serializers.DictField()
    subscription_mrr = serializers.DictField()
    featured_listing_fees = serializers.DictField()


class AdminSubscriptionItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    agent_id = serializers.UUIDField(source='agent.id')
    agent = serializers.CharField(source='agent.full_name')
    plan = serializers.CharField(source='plan.name', default="Starter")
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    amount_formatted = serializers.SerializerMethodField()
    date_started = serializers.SerializerMethodField()
    next_renewal = serializers.SerializerMethodField()
    status = serializers.CharField()

    def get_amount_formatted(self, obj):
        return f"N{obj.amount:,.0f}"

    def get_date_started(self, obj):
        return obj.date_started.strftime("%b %d")

    def get_next_renewal(self, obj):
        return obj.next_renewal.strftime("%b %d")


class SubscriptionsResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    header_stats = FinanceHeaderStatsSerializer()
    plans = PlanManagementSerializer(many=True)
    results = AdminSubscriptionItemSerializer(many=True)


class AdminListingFeatureItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    listing_id = serializers.UUIDField(source='listing.id')
    target_id = serializers.SerializerMethodField()
    agent = serializers.CharField(source='listing.agent.full_name')
    subscription_type = serializers.SerializerMethodField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    amount_formatted = serializers.SerializerMethodField()
    date_started = serializers.SerializerMethodField()
    date_due = serializers.SerializerMethodField()
    status = serializers.CharField()

    def get_target_id(self, obj):
        short_id = str(obj.listing.id).replace('-', '').upper()[:6]
        return f"#{short_id}"

    def get_subscription_type(self, obj):
        if obj.featured_plan:
            return obj.featured_plan.name
        return "7 day featured"

    def get_amount_formatted(self, obj):
        return f"N{obj.amount:,.0f}"

    def get_date_started(self, obj):
        return obj.date_started.strftime("%b %d")

    def get_date_due(self, obj):
        return obj.date_due.strftime("%b %d")


class FeaturesResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    header_stats = FinanceHeaderStatsSerializer()
    plans = FeaturedPlanManagementSerializer(many=True)
    results = AdminListingFeatureItemSerializer(many=True)


class RevenueOverviewResponseSerializer(serializers.Serializer):
    header_stats = serializers.DictField()
    chart_data = serializers.ListField()
    results = serializers.ListField()


class AdminSubscriptionDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    agent_id = serializers.UUIDField(source='agent.id')
    agent_name = serializers.CharField(source='agent.full_name')
    agent_email = serializers.CharField(source='agent.email')
    profile_picture = serializers.SerializerMethodField()
    plan_name = serializers.CharField(source='plan.name', default="Standard plan")
    date_started = serializers.SerializerMethodField()
    date_ending = serializers.SerializerMethodField()
    status = serializers.CharField()
    listings = serializers.SerializerMethodField()

    def get_profile_picture(self, obj):
        request = self.context.get('request')
        pic = None
        if hasattr(obj.agent, 'agent_profile') and obj.agent.agent_profile and obj.agent.agent_profile.profile_picture:
            pic = obj.agent.agent_profile.profile_picture

        if pic and hasattr(pic, 'url'):
            if request:
                return request.build_absolute_uri(pic.url)
            return pic.url
        return None

    def get_date_started(self, obj):
        return obj.date_started.strftime("%b %d")

    def get_date_ending(self, obj):
        return obj.next_renewal.strftime("%b %d")

    def get_listings(self, obj):
        from .serializers import OverviewListingItemSerializer
        request = self.context.get('request')
        listings = obj.agent.listings.all().order_by('-created_at')
        return OverviewListingItemSerializer(listings, many=True, context={'request': request}).data


class AdminFeatureDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    listing = AdminPropertyDetailSerializer()
    agent = serializers.SerializerMethodField()
    feature_info = serializers.SerializerMethodField()

    def get_agent(self, obj):
        agent_user = obj.listing.agent
        return {
            "id": str(agent_user.id),
            "name": agent_user.full_name,
            "email": agent_user.email,
            "phone": getattr(agent_user.agent_profile, 'phone_number', None) if hasattr(agent_user, 'agent_profile') else getattr(agent_user, 'phone', None)
        }

    def get_feature_info(self, obj):
        short_id = str(obj.listing.id).replace('-', '').upper()[:6]
        return {
            "property_id": f"#{short_id}",
            "address": obj.listing.address,
            "price": f"N{obj.listing.price:,.0f}",
            "feature_type": obj.featured_plan.name if obj.featured_plan else "14day plan",
            "starting_date": obj.date_started.strftime("%d %b %Y"),
            "expiring_date": obj.date_due.strftime("%d %b %Y"),
            "amount": f"N{obj.amount:,.0f}"
        }






