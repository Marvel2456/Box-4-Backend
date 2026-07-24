from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import SavedListing
from agents.models import Listing
from agents.serializers import ListingSerializer

User = get_user_model()

class SavedListingSerializer(serializers.ModelSerializer):
    listing_details = ListingSerializer(source='listing', read_only=True)
    listing_id = serializers.PrimaryKeyRelatedField(
        queryset=Listing.objects.all(), 
        source='listing', 
        write_only=True
    )

    class Meta:
        model = SavedListing
        fields = ('id', 'buyer', 'listing_id', 'listing_details', 'created_at')
        read_only_fields = ('id', 'buyer', 'created_at')

    def validate(self, attrs):
        request = self.context.get('request')
        buyer = request.user
        listing = attrs.get('listing')

        if SavedListing.objects.filter(buyer=buyer, listing=listing).exists():
            raise serializers.ValidationError("You have already saved this property listing.")

        return attrs


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
