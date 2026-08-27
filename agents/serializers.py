from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Listing, ListingImage, Category
from profiles.models import AgentProfile

User = get_user_model()

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

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
    cover_photo_url = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional specific image URL or path to mark as the primary thumbnail/cover photo."
    )
    image_urls = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
        help_text="List of media URLs (from POST /api/v1/media/upload/) to attach to this listing."
    )
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
            'is_featured', 'views_count', 'inquiries_count', 'cover_photo', 'cover_photo_url',
            'images', 'image_urls', 'image_ids', 'uploaded_images', 'created_at', 'updated_at'
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

    def _clean_media_path(self, url_str):
        if not url_str:
            return ""
        from urllib.parse import urlparse
        clean_path = str(url_str).strip()
        if '/media/' in clean_path:
            clean_path = clean_path.split('/media/', 1)[1]
        elif clean_path.startswith('http://') or clean_path.startswith('https://'):
            clean_path = urlparse(clean_path).path.lstrip('/')
        return clean_path

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
        cover_photo_url = validated_data.pop('cover_photo_url', None) or self.initial_data.get('cover_photo_url') or self.initial_data.get('thumbnail_url') or self.initial_data.get('cover_photo')
        image_urls = validated_data.pop('image_urls', [])
        image_ids = validated_data.pop('image_ids', [])
        uploaded_images = validated_data.pop('uploaded_images', [])

        validated_data['agent'] = self.context['request'].user
        listing = Listing.objects.create(**validated_data)

        target_cover_path = self._clean_media_path(cover_photo_url) if cover_photo_url else None
        has_cover = False

        # 1. Attach images by URL
        if image_urls:
            for idx, url_str in enumerate(image_urls):
                if not url_str:
                    continue
                clean_path = self._clean_media_path(url_str)
                is_cover_photo = False
                if target_cover_path:
                    if clean_path == target_cover_path:
                        is_cover_photo = True
                        has_cover = True
                elif idx == 0 and not has_cover:
                    is_cover_photo = True
                    has_cover = True

                ListingImage.objects.create(
                    listing=listing,
                    image=clean_path,
                    is_cover=is_cover_photo
                )

        # Explicit target cover photo URL creation if not present in image_urls list
        if target_cover_path and not has_cover:
            ListingImage.objects.create(
                listing=listing,
                image=target_cover_path,
                is_cover=True
            )
            has_cover = True

        # 2. Attach pre-uploaded images by ID (Step 2 flow)
        if image_ids:
            pre_uploaded = ListingImage.objects.filter(id__in=image_ids)
            for idx, img_obj in enumerate(pre_uploaded):
                img_obj.listing = listing
                if not has_cover:
                    img_obj.is_cover = True
                    has_cover = True
                img_obj.save()

        # 3. Attach direct uploaded files
        if uploaded_images:
            for idx, img in enumerate(uploaded_images):
                ListingImage.objects.create(
                    listing=listing,
                    image=img,
                    is_cover=(not has_cover and idx == 0)
                )
                if not has_cover and idx == 0:
                    has_cover = True

        return listing

    def update(self, instance, validated_data):
        cover_photo_url = validated_data.pop('cover_photo_url', None) or self.initial_data.get('cover_photo_url') or self.initial_data.get('thumbnail_url') or self.initial_data.get('cover_photo')
        image_urls = validated_data.pop('image_urls', None)
        image_ids = validated_data.pop('image_ids', None)
        uploaded_images = validated_data.pop('uploaded_images', None)

        listing = super().update(instance, validated_data)

        target_cover_path = self._clean_media_path(cover_photo_url) if cover_photo_url else None
        has_cover = instance.images.filter(is_cover=True).exists()

        if target_cover_path:
            # Unset previous cover photos
            instance.images.filter(is_cover=True).update(is_cover=False)
            has_cover = False

        if image_urls is not None:
            for idx, url_str in enumerate(image_urls):
                if not url_str:
                    continue
                clean_path = self._clean_media_path(url_str)
                is_cover_photo = False
                if target_cover_path:
                    if clean_path == target_cover_path:
                        is_cover_photo = True
                        has_cover = True
                elif idx == 0 and not has_cover:
                    is_cover_photo = True
                    has_cover = True

                ListingImage.objects.create(
                    listing=listing,
                    image=clean_path,
                    is_cover=is_cover_photo
                )

        if target_cover_path and not has_cover:
            # Check if image already exists under listing
            existing = instance.images.filter(image__contains=target_cover_path.split('/')[-1]).first()
            if existing:
                existing.is_cover = True
                existing.save()
            else:
                ListingImage.objects.create(
                    listing=listing,
                    image=target_cover_path,
                    is_cover=True
                )

        if image_ids is not None:
            pre_uploaded = ListingImage.objects.filter(id__in=image_ids)
            for idx, img_obj in enumerate(pre_uploaded):
                img_obj.listing = listing
                if not has_cover:
                    img_obj.is_cover = True
                    has_cover = True
                img_obj.save()

        if uploaded_images is not None:
            for idx, img in enumerate(uploaded_images):
                ListingImage.objects.create(
                    listing=listing,
                    image=img,
                    is_cover=(not has_cover and idx == 0)
                )
                if not has_cover and idx == 0:
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
