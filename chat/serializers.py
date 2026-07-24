from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Message
from agents.models import Listing

User = get_user_model()

class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    receiver_name = serializers.CharField(source='receiver.full_name', read_only=True)
    sender_email = serializers.CharField(source='sender.email', read_only=True)
    receiver_email = serializers.CharField(source='receiver.email', read_only=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True, default=None)

    class Meta:
        model = Message
        fields = (
            'id', 'sender', 'sender_name', 'sender_email',
            'receiver', 'receiver_name', 'receiver_email',
            'listing', 'listing_title', 'message', 'timestamp'
        )
        read_only_fields = ('id', 'sender', 'timestamp')


class InitiateChatSerializer(serializers.Serializer):
    receiver_id = serializers.UUIDField(required=False)
    listing_id = serializers.UUIDField(required=False)
    message = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get('receiver_id') and not attrs.get('listing_id'):
            raise serializers.ValidationError("Either 'receiver_id' or 'listing_id' must be provided to initiate a chat.")
        return attrs


class SendMessageSerializer(serializers.Serializer):
    receiver_id = serializers.UUIDField(required=True, help_text="UUID of the message receiver")
    message = serializers.CharField(required=True, help_text="Message text content")
    listing_id = serializers.UUIDField(required=False, allow_null=True, help_text="Optional associated property listing UUID")


class ChatPartnerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    role = serializers.CharField()
    profile_picture = serializers.URLField(allow_null=True)


class ConversationPreviewSerializer(serializers.Serializer):
    chat_partner = ChatPartnerSerializer()
    last_message = serializers.CharField()
    last_message_time = serializers.DateTimeField()


class ContactAgentResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    chat_message = MessageSerializer()


