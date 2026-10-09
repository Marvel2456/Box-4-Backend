from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils import timezone
import pusher
from django.conf import settings

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import ChatRoom, Message
from .serializers import (
    MessageSerializer, 
    InitiateChatSerializer, 
    SendMessageSerializer,
    ConversationPreviewSerializer,
    ContactAgentResponseSerializer,
    MarkReadSerializer,
    UnreadCountSerializer,
    PusherAuthSerializer
)
from agents.models import Listing
from core.firebase import send_push_notification

User = get_user_model()


def get_configured_pusher_client():
    if settings.PUSHER_APP_ID and settings.PUSHER_KEY and settings.PUSHER_SECRET:
        try:
            return pusher.Pusher(
                app_id=settings.PUSHER_APP_ID,
                key=settings.PUSHER_KEY,
                secret=settings.PUSHER_SECRET,
                cluster=settings.PUSHER_CLUSTER,
                ssl=True
            )
        except Exception:
            return None
    return None


class PusherAuthView(generics.GenericAPIView):
    """
    Pusher Channel Authentication Endpoint.
    Authenticates private channels (e.g. private-chat-<chatroom_id>, private-user-<user_id>).
    """
    serializer_class = PusherAuthSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=PusherAuthSerializer,
        responses={
            200: openapi.Response(description="Pusher auth response payload"),
            403: openapi.Response(description="Forbidden - User not authorized for channel"),
            503: openapi.Response(description="Pusher service not configured")
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        socket_id = serializer.validated_data['socket_id']
        channel_name = serializer.validated_data['channel_name']

        pusher_client = get_configured_pusher_client()
        if not pusher_client:
            return Response(
                {"error": "Pusher service is not configured on the server."}, 
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # 1. Authorize ChatRoom channels (e.g., 'private-chat-<room_id>', 'private-chatroom-<room_id>', 'private-chat_<room_id>')
        if channel_name.startswith(('private-chat-', 'private-chatroom-', 'private-chat_')):
            room_identifier = (
                channel_name.replace('private-chat-', '')
                            .replace('private-chatroom-', '')
                            .replace('private-chat_', '')
            )
            is_authorized = (
                ChatRoom.objects.filter(id=room_identifier, participants=request.user).exists()
                or ChatRoom.objects.filter(channel_name=channel_name, participants=request.user).exists()
            )
            if not is_authorized:
                return Response(
                    {"error": "Forbidden: You are not a participant in this chatroom."}, 
                    status=status.HTTP_403_FORBIDDEN
                )

        # 2. Authorize User personal channels (e.g., 'private-user-<user_id>', 'private-user_<user_id>')
        elif channel_name.startswith(('private-user-', 'private-user_')):
            user_identifier = (
                channel_name.replace('private-user-', '')
                            .replace('private-user_', '')
            )
            if str(request.user.id) != str(user_identifier):
                return Response(
                    {"error": "Forbidden: You cannot subscribe to another user's personal channel."}, 
                    status=status.HTTP_403_FORBIDDEN
                )

        # 3. For any other private channel, reject by default
        elif channel_name.startswith('private-'):
            return Response(
                {"error": "Forbidden: Unauthorized channel subscription."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # Generate Pusher authentication signature
        try:
            auth_response = pusher_client.authenticate(
                channel=channel_name,
                socket_id=socket_id
            )
            return Response(auth_response, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Failed to authenticate channel: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class ChatViewSet(viewsets.GenericViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_pusher_client(self):
        return get_configured_pusher_client()

    @swagger_auto_schema(
        request_body=PusherAuthSerializer,
        responses={200: openapi.Response(description="Pusher auth response payload")}
    )
    @action(detail=False, methods=['post'], url_path='pusher/auth')
    def pusher_auth(self, request):
        auth_view = PusherAuthView.as_view()
        return auth_view(request._request)

    @swagger_auto_schema(request_body=SendMessageSerializer, responses={201: MessageSerializer})
    @action(detail=False, methods=['post'])
    def send(self, request):
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        receiver_id = serializer.validated_data.get('receiver_id')
        chatroom_id = serializer.validated_data.get('chatroom_id')
        msg_text = serializer.validated_data.get('message')
        listing_id = serializer.validated_data.get('listing_id')

        room = None
        receiver = None

        if chatroom_id:
            room = ChatRoom.objects.filter(id=chatroom_id, participants=request.user).first()
            if not room:
                return Response({"error": "ChatRoom not found or you are not a participant."}, status=status.HTTP_404_NOT_FOUND)
            # Find the other participant
            receiver = room.participants.exclude(id=request.user.id).first()

        if receiver_id and not receiver:
            try:
                receiver = User.objects.get(id=receiver_id)
            except (User.DoesNotExist, ValueError):
                return Response({"error": "Receiver user not found."}, status=status.HTTP_404_NOT_FOUND)

        if not receiver:
            return Response({"error": "Could not determine message receiver."}, status=status.HTTP_400_BAD_REQUEST)

        if receiver == request.user:
            return Response({"error": "You cannot send messages to yourself."}, status=status.HTTP_400_BAD_REQUEST)

        listing_obj = None
        if listing_id:
            listing_obj = Listing.objects.filter(id=listing_id).first()

        if not room:
            room = ChatRoom.get_or_create_room(request.user, receiver, listing_obj)

        # Save message to database linked to chatroom
        message = Message.objects.create(
            chatroom=room,
            sender=request.user,
            receiver=receiver,
            listing=listing_obj or room.listing,
            message=msg_text
        )

        # Create In-App Notification
        from notifications.models import Notification
        Notification.objects.create(
            recipient=receiver,
            sender=request.user,
            notification_type='message',
            title='New Message',
            message=f"{request.user.full_name}: {msg_text[:100]}",
            listing=listing_obj or room.listing
        )

        # Calculate receiver unread counts (strictly consistent with active conversations)
        receiver_unread_total = Message.objects.filter(
            receiver=receiver, 
            is_read=False,
            chatroom__isnull=False
        ).exclude(
            sender__is_deleted=True
        ).exclude(
            sender__is_active=False
        ).count()

        # Broadcast Pusher Real-Time Events
        pusher_client = self.get_pusher_client()
        if pusher_client:
            message_payload = MessageSerializer(message).data
            try:
                # 1. Broadcast to specific chatroom channel
                pusher_client.trigger(
                    room.channel_name,
                    'new_message',
                    message_payload
                )
                # 2. Broadcast to receiver personal private channel for live update & instant badge count
                pusher_client.trigger(
                    f'private-user-{receiver.id}',
                    'new_message',
                    message_payload
                )
                pusher_client.trigger(
                    f'private-user-{receiver.id}',
                    'unread_count_update',
                    {
                        'unread_messages_count': receiver_unread_total,
                        'chatroom_id': str(room.id)
                    }
                )
                pusher_client.trigger(
                    f'private-user-{receiver.id}',
                    'new_notification',
                    {
                        'type': 'message',
                        'title': 'New Message',
                        'message': f"{request.user.full_name}: {msg_text[:100]}",
                        'chatroom_id': str(room.id),
                        'channel_name': room.channel_name
                    }
                )
                # Backwards-compatibility triggers
                pusher_client.trigger(
                    f'private-chat_{receiver.id}',
                    'new_message',
                    message_payload
                )
                pusher_client.trigger(
                    f'user_{receiver.id}',
                    'unread_count_update',
                    {
                        'unread_messages_count': receiver_unread_total,
                        'chatroom_id': str(room.id)
                    }
                )
                pusher_client.trigger(
                    f'user_{receiver.id}',
                    'new_notification',
                    {
                        'type': 'message',
                        'title': 'New Message',
                        'message': f"{request.user.full_name}: {msg_text[:100]}",
                        'chatroom_id': str(room.id),
                        'channel_name': room.channel_name
                    }
                )
            except Exception:
                pass

        # Dispatch FCM Push Notification in background
        send_push_notification(
            user=receiver,
            title=f"New message from {request.user.full_name}",
            body=msg_text[:120],
            data={
                "type": "chat",
                "chatroom_id": str(room.id),
                "channel_name": room.channel_name,
                "sender_id": str(request.user.id),
                "sender_name": str(request.user.full_name)
            }
        )

        serializer = MessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        responses={200: MessageSerializer(many=True)},
        manual_parameters=[
            openapi.Parameter('identifier', openapi.IN_PATH, description="UUID of the chat partner or ChatRoom ID", type=openapi.TYPE_STRING)
        ]
    )
    @action(detail=False, methods=['get'], url_path='history/(?P<identifier>[^/.]+)')
    def history(self, request, identifier=None):
        room = None
        # Check if identifier is a chatroom ID
        try:
            room = ChatRoom.objects.filter(id=identifier, participants=request.user).first()
        except Exception:
            room = None

        partner = None
        if not room:
            # Identifier is a partner User ID
            try:
                partner = User.objects.get(id=identifier)
                room = ChatRoom.objects.filter(participants=request.user).filter(participants=partner).first()
            except (User.DoesNotExist, ValueError):
                return Response({"error": "Chat conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        if not room and partner:
            room = ChatRoom.get_or_create_room(request.user, partner)

        if not room:
            return Response([], status=status.HTTP_200_OK)

        messages = room.messages.all().order_by('timestamp')

        # Automatically mark unread messages received by request.user as read
        unread_messages = room.messages.filter(receiver=request.user, is_read=False)
        if unread_messages.exists():
            now = timezone.now()
            unread_messages.update(is_read=True, read_at=now)

            # Mark matching in-app notifications as read
            from notifications.models import Notification
            other_user = room.participants.exclude(id=request.user.id).first()
            if other_user:
                Notification.objects.filter(recipient=request.user, sender=other_user, is_read=False).update(is_read=True)

            # Calculate updated unread count for request.user
            user_unread_total = Message.objects.filter(
                receiver=request.user, 
                is_read=False,
                chatroom__isnull=False
            ).exclude(
                sender__is_deleted=True
            ).exclude(
                sender__is_active=False
            ).count()

            # Broadcast read receipts via Pusher
            pusher_client = self.get_pusher_client()
            if pusher_client:
                try:
                    pusher_client.trigger(
                        room.channel_name,
                        'messages_read',
                        {
                            'chatroom_id': str(room.id),
                            'reader_id': str(request.user.id),
                            'read_at': now.isoformat()
                        }
                    )
                    pusher_client.trigger(
                        f'private-user-{request.user.id}',
                        'unread_count_update',
                        {
                            'unread_messages_count': user_unread_total,
                            'chatroom_id': str(room.id)
                        }
                    )
                    pusher_client.trigger(
                        f'user_{request.user.id}',
                        'unread_count_update',
                        {
                            'unread_messages_count': user_unread_total,
                            'chatroom_id': str(room.id)
                        }
                    )
                    if other_user:
                        pusher_client.trigger(
                            f'private-user-{other_user.id}',
                            'messages_read',
                            {
                                'chatroom_id': str(room.id),
                                'reader_id': str(request.user.id),
                                'read_at': now.isoformat()
                            }
                        )
                except Exception:
                    pass

        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(responses={200: ConversationPreviewSerializer(many=True)})
    @action(detail=False, methods=['get'])
    def conversations(self, request):
        user = request.user
        rooms = ChatRoom.objects.filter(participants=user).prefetch_related('participants', 'messages', 'listing').order_by('-updated_at')

        results = []
        for room in rooms:
            partner = room.participants.exclude(id=user.id).first()
            if not partner or getattr(partner, 'is_deleted', False) or not getattr(partner, 'is_active', True):
                continue

            last_msg = room.messages.order_by('-timestamp').first()
            unread_count = room.messages.filter(
                receiver=user, 
                is_read=False
            ).exclude(
                sender__is_deleted=True
            ).exclude(
                sender__is_active=False
            ).count()

            profile_pic = None
            if hasattr(partner, 'agent_profile') and partner.agent_profile.profile_picture:
                profile_pic = request.build_absolute_uri(partner.agent_profile.profile_picture.url)
            elif hasattr(partner, 'buyer_profile') and partner.buyer_profile.profile_picture:
                profile_pic = request.build_absolute_uri(partner.buyer_profile.profile_picture.url)

            results.append({
                "chatroom_id": str(room.id),
                "channel_name": room.channel_name,
                "event": "new_message",
                "chat_partner": {
                    "id": str(partner.id),
                    "email": partner.email,
                    "full_name": partner.full_name or partner.email,
                    "role": partner.role,
                    "profile_picture": profile_pic
                },
                "last_message": last_msg.message if last_msg else "",
                "last_message_time": last_msg.timestamp.isoformat() if last_msg else room.created_at.isoformat(),
                "unread_count": unread_count,
                "listing_id": str(room.listing.id) if room.listing else None,
                "listing_title": room.listing.title if room.listing else None,
            })

        # Sort by last message time descending
        results.sort(key=lambda x: x['last_message_time'], reverse=True)
        return Response(results, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        request_body=MarkReadSerializer,
        responses={200: openapi.Response(description="Messages marked as read successfully")}
    )
    @action(detail=False, methods=['post'], url_path='mark-read')
    def mark_read(self, request):
        serializer = MarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        chatroom_id = serializer.validated_data.get('chatroom_id')
        partner_id = serializer.validated_data.get('partner_id')

        room = None
        if chatroom_id:
            room = ChatRoom.objects.filter(id=chatroom_id, participants=request.user).first()
        elif partner_id:
            partner = User.objects.filter(id=partner_id).first()
            if partner:
                room = ChatRoom.objects.filter(participants=request.user).filter(participants=partner).first()

        if not room:
            return Response({"error": "Chat conversation not found."}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        updated_count = room.messages.filter(receiver=request.user, is_read=False).update(is_read=True, read_at=now)

        # Mark in-app notifications read
        from notifications.models import Notification
        other_user = room.participants.exclude(id=request.user.id).first()
        if other_user:
            Notification.objects.filter(recipient=request.user, sender=other_user, is_read=False).update(is_read=True)

        # Calculate updated unread count for request.user
        user_unread_total = Message.objects.filter(
            receiver=request.user, 
            is_read=False,
            chatroom__isnull=False
        ).exclude(
            sender__is_deleted=True
        ).exclude(
            sender__is_active=False
        ).count()

        # Real-time Pusher updates
        pusher_client = self.get_pusher_client()
        if pusher_client:
            try:
                # Notify room participants that messages were read (seen checkmarks)
                pusher_client.trigger(
                    room.channel_name,
                    'messages_read',
                    {
                        'chatroom_id': str(room.id),
                        'reader_id': str(request.user.id),
                        'read_at': now.isoformat()
                    }
                )
                # Update user's personal unread count badge
                pusher_client.trigger(
                    f'private-user-{request.user.id}',
                    'unread_count_update',
                    {
                        'unread_messages_count': user_unread_total,
                        'chatroom_id': str(room.id)
                    }
                )
                pusher_client.trigger(
                    f'user_{request.user.id}',
                    'unread_count_update',
                    {
                        'unread_messages_count': user_unread_total,
                        'chatroom_id': str(room.id)
                    }
                )
                # Notify other participant's personal channel that messages were read
                if other_user:
                    pusher_client.trigger(
                        f'private-user-{other_user.id}',
                        'messages_read',
                        {
                            'chatroom_id': str(room.id),
                            'reader_id': str(request.user.id),
                            'read_at': now.isoformat()
                        }
                    )
            except Exception:
                pass

        return Response({
            "message": "Messages marked as read successfully.",
            "marked_count": updated_count,
            "unread_count": user_unread_total
        }, status=status.HTTP_200_OK)

    @swagger_auto_schema(responses={200: UnreadCountSerializer})
    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = Message.objects.filter(
            receiver=request.user, 
            is_read=False,
            chatroom__isnull=False
        ).exclude(
            sender__is_deleted=True
        ).exclude(
            sender__is_active=False
        ).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)


class ContactAgentView(generics.GenericAPIView):
    serializer_class = InitiateChatSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_pusher_client(self):
        return get_configured_pusher_client()

    @swagger_auto_schema(request_body=InitiateChatSerializer, responses={201: ContactAgentResponseSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        receiver_id = serializer.validated_data.get('receiver_id')
        listing_id = serializer.validated_data.get('listing_id')
        custom_message = serializer.validated_data.get('message')

        receiver = None
        listing_obj = None

        if listing_id:
            try:
                listing_obj = Listing.objects.get(id=listing_id)
                receiver = listing_obj.agent
            except (Listing.DoesNotExist, ValueError):
                return Response({"error": "Property listing not found."}, status=status.HTTP_404_NOT_FOUND)

        if receiver_id and not receiver:
            try:
                receiver = User.objects.get(id=receiver_id)
            except (User.DoesNotExist, ValueError):
                return Response({"error": "Agent/user not found."}, status=status.HTTP_404_NOT_FOUND)

        if not receiver:
            return Response({"error": "Receiver not found."}, status=status.HTTP_404_NOT_FOUND)

        if receiver == request.user:
            return Response({"error": "You cannot initiate a chat conversation with yourself."}, status=status.HTTP_400_BAD_REQUEST)

        # Build initial message
        if custom_message and custom_message.strip():
            intro_msg = custom_message
        elif listing_obj:
            intro_msg = f"Hi {receiver.full_name}, I am interested in your property listing: '{listing_obj.title}' located at {listing_obj.address}."
        else:
            intro_msg = f"Hi {receiver.full_name}, I would like to connect with you regarding your property listings."

        # Get or create ChatRoom
        room = ChatRoom.get_or_create_room(request.user, receiver, listing_obj)

        # Save to database
        message = Message.objects.create(
            chatroom=room,
            sender=request.user,
            receiver=receiver,
            listing=listing_obj,
            message=intro_msg
        )

        # Create In-App Notification
        from notifications.models import Notification
        Notification.objects.create(
            recipient=receiver,
            sender=request.user,
            notification_type='inquiry',
            title='Property Inquiry',
            message=intro_msg,
            listing=listing_obj
        )

        # Calculate receiver unread count
        receiver_unread_total = Message.objects.filter(
            receiver=receiver, 
            is_read=False,
            chatroom__isnull=False
        ).exclude(
            sender__is_deleted=True
        ).exclude(
            sender__is_active=False
        ).count()

        # Trigger Pusher
        pusher_client = self.get_pusher_client()
        if pusher_client:
            message_payload = MessageSerializer(message).data
            try:
                # 1. Chatroom channel
                pusher_client.trigger(
                    room.channel_name,
                    'new_message',
                    message_payload
                )
                # 2. Receiver personal private channel
                pusher_client.trigger(
                    f'private-user-{receiver.id}',
                    'new_message',
                    message_payload
                )
                pusher_client.trigger(
                    f'private-user-{receiver.id}',
                    'unread_count_update',
                    {
                        'unread_messages_count': receiver_unread_total,
                        'chatroom_id': str(room.id)
                    }
                )
                pusher_client.trigger(
                    f'private-user-{receiver.id}',
                    'new_notification',
                    {
                        'type': 'inquiry',
                        'title': 'Property Inquiry',
                        'message': intro_msg,
                        'chatroom_id': str(room.id),
                        'channel_name': room.channel_name
                    }
                )
                # Backwards compatibility triggers
                pusher_client.trigger(
                    f'private-chat_{receiver.id}',
                    'new_message',
                    message_payload
                )
                pusher_client.trigger(
                    f'user_{receiver.id}',
                    'unread_count_update',
                    {
                        'unread_messages_count': receiver_unread_total,
                        'chatroom_id': str(room.id)
                    }
                )
                pusher_client.trigger(
                    f'user_{receiver.id}',
                    'new_notification',
                    {
                        'type': 'inquiry',
                        'title': 'Property Inquiry',
                        'message': intro_msg,
                        'chatroom_id': str(room.id),
                        'channel_name': room.channel_name
                    }
                )
            except Exception:
                pass

        # Dispatch FCM Push Notification
        send_push_notification(
            user=receiver,
            title=f"Property Inquiry from {request.user.full_name}",
            body=intro_msg[:120],
            data={
                "type": "inquiry",
                "chatroom_id": str(room.id),
                "channel_name": room.channel_name,
                "sender_id": str(request.user.id),
                "listing_id": str(listing_obj.id) if listing_obj else ""
            }
        )

        return Response({
            "message": "Chat conversation initiated successfully.",
            "chatroom_id": str(room.id),
            "channel_name": room.channel_name,
            "event": "new_message",
            "chat_message": MessageSerializer(message).data
        }, status=status.HTTP_201_CREATED)
