from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Listing, ListingImage
from profiles.models import AgentProfile

User = get_user_model()

class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ('id', 'image', 'is_cover', 'created_at')


class ListingImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(required=False, help_text="Property photo file to upload.")
    listing_id = serializers.UUIDField(required=False, allow_null=True, help_text="Optional ID of listing to attach images to.")


class ListingSerializer(serializers.ModelSerializer):
    images = ListingImageSerializer(many=True, read_only=True)
    cover_photo = serializers.SerializerMethodField()
    inquiries_count = serializers.SerializerMethodField()
    image_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        help_text="List of pre-uploaded image UUIDs to attach to this listing."
    )
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(max_length=10000000, allow_empty_file=False, use_url=False),
        write_only=True,
        required=False,
        help_text="Direct multipart image files to upload."
    )
    agent_name = serializers.CharField(source='agent.full_name', read_only=True)

    class Meta:
        model = Listing
        fields = (
            'id', 'agent', 'agent_name', 'title', 'category', 'price', 'address',
            'latitude', 'longitude', 'bedrooms', 'bathrooms', 'balconies',
            'total_rooms', 'facilities', 'status', 'is_published', 'is_boosted',
            'is_featured', 'views_count', 'inquiries_count', 'cover_photo',
            'images', 'image_ids', 'uploaded_images', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'agent', 'is_boosted', 'is_featured', 'created_at', 'updated_at')

    def get_cover_photo(self, obj):
        cover = obj.images.filter(is_cover=True).first()
        if not cover:
            cover = obj.images.first()
        if cover and cover.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(cover.image.url)
            return cover.image.url
        return None

    def get_inquiries_count(self, obj):
        from chat.models import Message
        return Message.objects.filter(listing=obj).count()

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
        image_ids = validated_data.pop('image_ids', [])
        uploaded_images = validated_data.pop('uploaded_images', [])
        # Assign current request user as agent
        validated_data['agent'] = self.context['request'].user
        listing = Listing.objects.create(**validated_data)

        has_cover = False

        # Attach pre-uploaded images by ID (Step 2 flow)
        if image_ids:
            pre_uploaded = ListingImage.objects.filter(id__in=image_ids)
            for idx, img_obj in enumerate(pre_uploaded):
                img_obj.listing = listing
                if not has_cover:
                    img_obj.is_cover = True
                    has_cover = True
                img_obj.save()

        # Attach direct uploaded images
        if uploaded_images:
            for idx, img in enumerate(uploaded_images):
                ListingImage.objects.create(
                    listing=listing,
                    image=img,
                    is_cover=(not has_cover and idx == 0)
                )
                if idx == 0:
                    has_cover = True

        return listing


class AgentDashboardMetricsSerializer(serializers.Serializer):
    active_listings = serializers.DictField()
    new_inquiries = serializers.DictField()
    subscription = serializers.DictField()
    views = serializers.DictField()


class AgentDashboardResponseSerializer(serializers.Serializer):
    greeting = serializers.CharField()
    agent = serializers.DictField()
    metrics = AgentDashboardMetricsSerializer()
    active_listings = ListingSerializer(many=True)
