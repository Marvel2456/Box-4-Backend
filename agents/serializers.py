from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Listing, ListingImage
from profiles.models import AgentProfile

User = get_user_model()

class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ('id', 'image', 'is_cover')


class ListingSerializer(serializers.ModelSerializer):
    images = ListingImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(max_length=10000000, allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )
    agent_name = serializers.CharField(source='agent.full_name', read_only=True)

    class Meta:
        model = Listing
        fields = (
            'id', 'agent', 'agent_name', 'title', 'category', 'price', 'address',
            'latitude', 'longitude', 'bedrooms', 'bathrooms', 'balconies',
            'total_rooms', 'facilities', 'is_published', 'is_boosted',
            'is_featured', 'images', 'uploaded_images', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'agent', 'is_boosted', 'is_featured', 'created_at', 'updated_at')

    def validate(self, attrs):
        request = self.context.get('request')
        # Only validate limits during creation (POST)
        if request and request.method == 'POST':
            user = request.user
            if user.role != 'agent':
                raise serializers.ValidationError("Only users registered as agents can create listings.")
                
            try:
                profile = user.agent_profile
            except AgentProfile.DoesNotExist:
                raise serializers.ValidationError("Agent profile not found. Please complete profile registration.")

            plan = profile.plan
            if not plan:
                raise serializers.ValidationError("You do not have an active subscription plan. Please subscribe to list properties.")

            # Enforce total listing limits (0 means unlimited)
            if plan.max_listings > 0:
                current_count = Listing.objects.filter(agent=user).count()
                if current_count >= plan.max_listings:
                    raise serializers.ValidationError(
                        f"You have reached the maximum listing limit of {plan.max_listings} for the '{plan.name}' plan. Please upgrade to a higher plan."
                    )
        return attrs

    def create(self, validated_data):
        uploaded_images = validated_data.pop('uploaded_images', [])
        # Assign current request user as agent
        validated_data['agent'] = self.context['request'].user
        listing = Listing.objects.create(**validated_data)

        # Store images
        for idx, img in enumerate(uploaded_images):
            ListingImage.objects.create(
                listing=listing,
                image=img,
                is_cover=(idx == 0) # Mark the first uploaded image as cover
            )

        return listing
