from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Notification

User = get_user_model()

class NotificationSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True, default=None)
    sender_avatar = serializers.SerializerMethodField()
    listing_title = serializers.CharField(source='listing.title', read_only=True, default=None)
    listing_image = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            'id', 'recipient', 'sender', 'sender_name', 'sender_avatar',
            'notification_type', 'title', 'message',
            'listing', 'listing_title', 'listing_image',
            'is_read', 'created_at'
        )
        read_only_fields = ('id', 'recipient', 'created_at')

    def get_sender_avatar(self, obj):
        request = self.context.get('request')
        if not obj.sender:
            return None
        
        profile = getattr(obj.sender, 'agent_profile', None) or getattr(obj.sender, 'buyer_profile', None)
        if profile and getattr(profile, 'profile_picture', None):
            if request:
                return request.build_absolute_uri(profile.profile_picture.url)
            return profile.profile_picture.url
        return None

    def get_listing_image(self, obj):
        request = self.context.get('request')
        if obj.listing:
            first_image = obj.listing.images.first()
            if first_image and first_image.image:
                if request:
                    return request.build_absolute_uri(first_image.image.url)
                return first_image.image.url
        return None
