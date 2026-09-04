from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import SavedListing
from agents.models import Listing
from agents.serializers import ListingSerializer

User = get_user_model()


class SavedListingCreateSerializer(serializers.Serializer):
    listing_id = serializers.UUIDField(help_text="UUID of the property listing to save.")

    def to_internal_value(self, data):
        if isinstance(data, dict):
            mutable_data = data.copy()
            target_id = mutable_data.get('listing_id') or mutable_data.get('listing') or mutable_data.get('id')
            if target_id:
                mutable_data['listing_id'] = target_id
            return super().to_internal_value(mutable_data)
        return super().to_internal_value(data)

    def validate_listing_id(self, value):
        try:
            return Listing.objects.get(pk=value)
        except Listing.DoesNotExist:
            raise serializers.ValidationError("Property listing not found.")

    def validate(self, attrs):
        return attrs

    def create(self, validated_data):
        buyer = self.context['request'].user
        listing = validated_data['listing_id']
        return SavedListing.objects.create(buyer=buyer, listing=listing)


class SavedListingSerializer(serializers.ModelSerializer):
    listing_details = ListingSerializer(source='listing', read_only=True)

    class Meta:
        model = SavedListing
        fields = ('id', 'buyer', 'listing', 'listing_details', 'created_at')
        read_only_fields = ('id', 'buyer', 'listing', 'created_at')


class AgentDetailSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(source='agent_profile.phone_number', read_only=True, default=None)
    profile_picture = serializers.SerializerMethodField()
    agency_name = serializers.CharField(source='agent_profile.agency_name', read_only=True, default=None)
    license_number = serializers.CharField(source='agent_profile.license_number', read_only=True, default=None)
    rating = serializers.SerializerMethodField()
    bio = serializers.CharField(source='agent_profile.bio', read_only=True, default=None)
    total_listings_count = serializers.SerializerMethodField()
    date_joined = serializers.DateTimeField(read_only=True)
    listings = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'full_name', 'role', 'phone_number', 'profile_picture',
            'agency_name', 'license_number', 'rating', 'bio', 'date_joined',
            'total_listings_count', 'listings'
        )

    def get_profile_picture(self, obj):
        request = self.context.get('request')
        if hasattr(obj, 'agent_profile') and obj.agent_profile.profile_picture:
            if request:
                return request.build_absolute_uri(obj.agent_profile.profile_picture.url)
            return obj.agent_profile.profile_picture.url
        return None

    def get_rating(self, obj):
        if hasattr(obj, 'agent_profile') and obj.agent_profile.rating:
            return float(obj.agent_profile.rating)
        return 0.0

    def get_total_listings_count(self, obj):
        return Listing.objects.filter(agent=obj, is_published=True).count()

    def get_listings(self, obj):
        request = self.context.get('request')
        listings = Listing.objects.filter(agent=obj, is_published=True).order_by('-created_at')
        return ListingSerializer(listings, many=True, context={'request': request}).data


class TopLocationSerializer(serializers.Serializer):
    location = serializers.CharField()
    listings_count = serializers.IntegerField()
    cover_photo = serializers.CharField(allow_null=True)
    avg_price = serializers.DecimalField(max_digits=12, decimal_places=2)


class BuyerDashboardSerializer(serializers.Serializer):
    profile_picture = serializers.CharField(allow_null=True, required=False)
    user_location = serializers.DictField()
    nearest_properties = ListingSerializer(many=True)
    top_agents = AgentDetailSerializer(many=True)
    top_locations = TopLocationSerializer(many=True)
