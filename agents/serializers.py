from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Listing, ListingImage, Category, Tag
from profiles.models import AgentProfile

User = get_user_model()

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
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
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_details = CategorySerializer(source='category', read_only=True)
    tag = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True, required=False)
    tags = TagSerializer(source='tag', many=True, read_only=True)
    is_saved = serializers.SerializerMethodField()
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
            'id', 'agent', 'agent_name', 'title', 'category', 'category_name', 'category_details',
            'tag', 'tags', 'price', 'address', 'city', 'state', 'country',
            'latitude', 'longitude', 'bedrooms', 'bathrooms', 'balconies',
            'total_rooms', 'facilities', 'status', 'is_published', 'is_boosted',
            'is_featured', 'is_saved', 'views_count', 'inquiries_count', 'cover_photo', 'cover_photo_url',
            'images', 'image_urls', 'image_ids', 'uploaded_images', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'agent', 'is_boosted', 'is_featured', 'created_at', 'updated_at')

    def to_internal_value(self, data):
        if isinstance(data, dict):
            mutable_data = data.copy()
            cat = mutable_data.get('category') or mutable_data.get('category_id')
            if cat:
                import uuid
                if isinstance(cat, str):
                    try:
                        uuid.UUID(cat)
                    except ValueError:
                        category_obj = Category.objects.filter(name__iexact=cat).first()
                        if not category_obj:
                            category_obj = Category.objects.create(name=cat.capitalize())
                        mutable_data['category'] = str(category_obj.id)

            tags = mutable_data.get('tags') or mutable_data.get('tag_ids') or mutable_data.get('tag')
            if tags and isinstance(tags, list):
                import uuid
                tag_uuids = []
                for t in tags:
                    if isinstance(t, str):
                        try:
                            uuid.UUID(t)
                            tag_uuids.append(t)
                        except ValueError:
                            tag_obj = Tag.objects.filter(name__iexact=t).first()
                            if tag_obj:
                                tag_uuids.append(str(tag_obj.id))
                    elif hasattr(t, 'id'):
                        tag_uuids.append(str(t.id))
                mutable_data['tag'] = tag_uuids

            return super().to_internal_value(mutable_data)
        return super().to_internal_value(data)

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

    def get_is_saved(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated and getattr(request.user, 'role', None) == 'buyer':
            from buyers.models import SavedListing
            return SavedListing.objects.filter(buyer=request.user, listing=obj).exists()
        return False

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

            # Enforce KYC verification
            if not hasattr(profile, 'kyc') or profile.kyc.status != 'verified':
                raise serializers.ValidationError(
                    "Your account KYC is not verified. Please complete your NIN and CAC identity verification to list properties."
                )

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
        tags = validated_data.pop('tag', None)

        validated_data['agent'] = self.context['request'].user
        listing = Listing.objects.create(**validated_data)

        if tags is not None:
            listing.tag.set(tags)

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
        tags = validated_data.pop('tag', None)

        listing = super().update(instance, validated_data)

        if tags is not None:
            listing.tag.set(tags)

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


class AgentKYCSubmitSerializer(serializers.Serializer):
    nin_number = serializers.CharField(max_length=11, min_length=11, help_text="11-digit National Identity Number (NIN).")
    cac_number = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True, help_text="Optional CAC registration number (e.g. RC1234567 or BN7654321).")
    cac_company_type = serializers.ChoiceField(choices=[('co', 'Company (RC)'), ('bn', 'Business Name (BN)'), ('it', 'Incorporated Trustees')], default='co', required=False)
    agency_name = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)

    def validate_nin_number(self, value):
        val = str(value).strip()
        if not val.isdigit() or len(val) != 11:
            raise serializers.ValidationError("NIN must be an 11-digit number.")
        return val


class AgentKYCSerializer(serializers.ModelSerializer):
    agent_email = serializers.CharField(source='agent_profile.user.email', read_only=True)
    agent_name = serializers.CharField(source='agent_profile.user.full_name', read_only=True)

    class Meta:
        from profiles.models import AgentKYC
        model = AgentKYC
        fields = (
            'id', 'agent_email', 'agent_name', 'status', 'nin_number', 'nin_verified', 'cac_number',
            'cac_company_type', 'cac_verified', 'attempts_count',
            'failure_reason', 'submitted_at', 'verified_at', 'created_at', 'updated_at'
        )
        read_only_fields = fields

