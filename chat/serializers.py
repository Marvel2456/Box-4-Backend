from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ChatRoom, Message
from agents.models import Listing

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    receiver_name = serializers.CharField(source='receiver.full_name', read_only=True)
    sender_email = serializers.CharField(source='sender.email', read_only=True)
    receiver_email = serializers.CharField(source='receiver.email', read_only=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True, default=None)
    channel_name = serializers.CharField(source='chatroom.channel_name', read_only=True, default=None)
    event = serializers.CharField(default='new_message', read_only=True)

    class Meta:
        model = Message
        fields = (
            'id', 'chatroom', 'channel_name', 'event',
            'sender', 'sender_name', 'sender_email',
            'receiver', 'receiver_name', 'receiver_email',
            'listing', 'listing_title', 'message',
            'is_read', 'read_at', 'timestamp'
        )
        read_only_fields = ('id', 'chatroom', 'sender', 'is_read', 'read_at', 'timestamp')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Ensure UUID fields are converted to strings so standard JSON serializers (such as Pusher's) do not fail
        for key in ['id', 'chatroom', 'sender', 'receiver', 'listing']:
            if data.get(key) is not None:
                data[key] = str(data[key])
        return data


class InitiateChatSerializer(serializers.Serializer):
    receiver_id = serializers.UUIDField(required=False)
    listing_id = serializers.UUIDField(required=False)
    message = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs.get('receiver_id') and not attrs.get('listing_id'):
            raise serializers.ValidationError("Either 'receiver_id' or 'listing_id' must be provided to initiate a chat.")
        return attrs


class SendMessageSerializer(serializers.Serializer):
    receiver_id = serializers.UUIDField(required=False, help_text="UUID of the message receiver (optional if chatroom_id is provided)")
    chatroom_id = serializers.UUIDField(required=False, help_text="UUID of the existing ChatRoom (optional if receiver_id is provided)")
    message = serializers.CharField(required=True, help_text="Message text content")
    listing_id = serializers.UUIDField(required=False, allow_null=True, help_text="Optional associated property listing UUID")

    def validate(self, attrs):
        if not attrs.get('receiver_id') and not attrs.get('chatroom_id'):
            raise serializers.ValidationError("Either 'receiver_id' or 'chatroom_id' must be provided.")
        return attrs


class ChatPartnerSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    role = serializers.CharField()
    profile_picture = serializers.URLField(allow_null=True)
    is_blocked = serializers.BooleanField(default=False)
    is_blocked_by_me = serializers.BooleanField(default=False)


class ConversationPreviewSerializer(serializers.Serializer):
    chatroom_id = serializers.UUIDField()
    channel_name = serializers.CharField()
    event = serializers.CharField(default='new_message')
    chat_partner = ChatPartnerSerializer()
    last_message = serializers.CharField()
    last_message_time = serializers.DateTimeField()
    unread_count = serializers.IntegerField(default=0)
    listing_id = serializers.UUIDField(allow_null=True, required=False)
    listing_title = serializers.CharField(allow_null=True, required=False)
    is_blocked = serializers.BooleanField(default=False)


class ContactAgentResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    chatroom_id = serializers.UUIDField()
    channel_name = serializers.CharField()
    event = serializers.CharField(default='new_message')
    chat_message = MessageSerializer()


class MarkReadSerializer(serializers.Serializer):
    chatroom_id = serializers.UUIDField(required=False, help_text="UUID of the ChatRoom to mark all messages as read")
    partner_id = serializers.UUIDField(required=False, help_text="UUID of the chat partner to mark all messages as read")

    def validate(self, attrs):
        if not attrs.get('chatroom_id') and not attrs.get('partner_id'):
            raise serializers.ValidationError("Either 'chatroom_id' or 'partner_id' must be provided.")
        return attrs


class UnreadCountSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField()


class PusherAuthSerializer(serializers.Serializer):
    socket_id = serializers.CharField(required=True, help_text="Pusher client socket_id")
    channel_name = serializers.CharField(required=True, help_text="Channel name to authenticate (e.g., private-chat-<chatroom_id> or private-user-<user_id>)")


class BlockUserSerializer(serializers.Serializer):
    user_id = serializers.UUIDField(required=True, help_text="UUID of the user to block")
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255, default="", help_text="Optional reason for blocking")


class UnblockUserSerializer(serializers.Serializer):
    user_id = serializers.UUIDField(required=True, help_text="UUID of the user to unblock")


class BlockedUserItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    role = serializers.CharField()
    profile_picture = serializers.URLField(allow_null=True)
    reason = serializers.CharField(allow_null=True, allow_blank=True)
    blocked_at = serializers.DateTimeField()


class SubmitReportSerializer(serializers.Serializer):
    REPORT_TYPE_CHOICES = ('message', 'user', 'listing')

    report_type = serializers.ChoiceField(choices=REPORT_TYPE_CHOICES, default='message', help_text="Type of report: 'message', 'user', or 'listing'")
    reported_user_id = serializers.UUIDField(required=False, allow_null=True, help_text="UUID of reported user (optional if message_id provided)")
    message_id = serializers.UUIDField(required=False, allow_null=True, help_text="UUID of reported message (optional)")
    listing_id = serializers.UUIDField(required=False, allow_null=True, help_text="UUID of reported listing (optional)")
    reason = serializers.CharField(required=True, max_length=255, help_text="Reason for the report (e.g. 'Harassment', 'Abuse', 'Spam', 'Fraud')")
    description = serializers.CharField(required=False, allow_blank=True, default="", help_text="Detailed description of the issue")

    def validate(self, attrs):
        if not attrs.get('message_id') and not attrs.get('reported_user_id') and not attrs.get('listing_id'):
            raise serializers.ValidationError("At least one target ('message_id', 'reported_user_id', or 'listing_id') must be provided.")
        return attrs
