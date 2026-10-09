import logging
import json
from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
import pusher
from django.conf import settings

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import ChatRoom, Message, BlockedUser
from .serializers import (
    MessageSerializer, 
    InitiateChatSerializer, 
    SendMessageSerializer,
    ConversationPreviewSerializer,
    ContactAgentResponseSerializer,
    MarkReadSerializer,
    UnreadCountSerializer,
    PusherAuthSerializer,
    BlockUserSerializer,
    UnblockUserSerializer,
    BlockedUserItemSerializer,
    SubmitReportSerializer
)
from agents.models import Listing, Report
from core.firebase import send_push_notification

User = get_user_model()
logger = logging.getLogger(__name__)


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
        except Exception as e:
            logger.error("Failed to initialize Pusher client: %s", str(e))
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


class BlockUserView(generics.GenericAPIView):
    """
    Block an abusive or unwanted user.
    """
    serializer_class = BlockUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=BlockUserSerializer,
        responses={200: openapi.Response(description="User blocked successfully")}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data['user_id']
        reason = serializer.validated_data.get('reason', '')

        if str(request.user.id) == str(target_user_id):
            return Response({"error": "You cannot block yourself."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_user = User.objects.get(id=target_user_id)
        except (User.DoesNotExist, ValueError):
            return Response({"error": "Target user not found."}, status=status.HTTP_404_NOT_FOUND)

        block_obj, created = BlockedUser.objects.get_or_create(
            blocker=request.user,
            blocked=target_user,
            defaults={'reason': reason}
        )
        if not created and reason:
            block_obj.reason = reason
            block_obj.save(update_fields=['reason'])

        return Response({
            "message": f"Successfully blocked {target_user.full_name or target_user.email}.",
            "blocked_user_id": str(target_user.id)
        }, status=status.HTTP_200_OK)


class UnblockUserView(generics.GenericAPIView):
    """
    Unblock a previously blocked user.
    """
    serializer_class = UnblockUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=UnblockUserSerializer,
        responses={200: openapi.Response(description="User unblocked successfully")}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        target_user_id = serializer.validated_data['user_id']
        deleted_count, _ = BlockedUser.objects.filter(blocker=request.user, blocked_id=target_user_id).delete()

        return Response({
            "message": "User unblocked successfully.",
            "unblocked_user_id": str(target_user_id),
            "unblocked": deleted_count > 0
        }, status=status.HTTP_200_OK)


class BlockedUsersListView(generics.GenericAPIView):
    """
    List all users blocked by the authenticated user.
    """
    serializer_class = BlockedUserItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(responses={200: BlockedUserItemSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        blocks = BlockedUser.objects.filter(blocker=request.user).select_related('blocked').order_by('-created_at')

        results = []
        for b in blocks:
            user = b.blocked
            pic = None
            if hasattr(user, 'agent_profile') and user.agent_profile.profile_picture:
                pic = request.build_absolute_uri(user.agent_profile.profile_picture.url)
            elif hasattr(user, 'buyer_profile') and user.buyer_profile.profile_picture:
                pic = request.build_absolute_uri(user.buyer_profile.profile_picture.url)

            results.append({
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name or user.email,
                "role": user.role,
                "profile_picture": pic,
                "reason": b.reason,
                "blocked_at": b.created_at.isoformat()
            })

        return Response(results, status=status.HTTP_200_OK)


class SubmitReportView(generics.GenericAPIView):
    """
    Report an abusive user, message, or fraudulent property listing (App Store Guideline 1.2).
    """
    serializer_class = SubmitReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=SubmitReportSerializer,
        responses={201: openapi.Response(description="Report submitted successfully")}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        report_type = serializer.validated_data.get('report_type', 'message')
        message_id = serializer.validated_data.get('message_id')
        reported_user_id = serializer.validated_data.get('reported_user_id')
        listing_id = serializer.validated_data.get('listing_id')
        reason = serializer.validated_data.get('reason')
        description = serializer.validated_data.get('description', '')

        message_obj = None
        reported_user = None
        listing_obj = None

        if message_id:
            try:
                message_obj = Message.objects.get(id=message_id)
                reported_user = message_obj.sender
                listing_obj = message_obj.listing
                report_type = 'message'
            except (Message.DoesNotExist, ValueError):
                return Response({"error": "Referenced message not found."}, status=status.HTTP_404_NOT_FOUND)

        if reported_user_id and not reported_user:
            try:
                reported_user = User.objects.get(id=reported_user_id)
            except (User.DoesNotExist, ValueError):
                return Response({"error": "Reported user not found."}, status=status.HTTP_404_NOT_FOUND)

        if listing_id and not listing_obj:
            try:
                listing_obj = Listing.objects.get(id=listing_id)
                if not reported_user:
                    reported_user = listing_obj.agent
            except (Listing.DoesNotExist, ValueError):
                return Response({"error": "Reported listing not found."}, status=status.HTTP_404_NOT_FOUND)

        if reported_user and reported_user == request.user:
            return Response({"error": "You cannot submit a report against yourself."}, status=status.HTTP_400_BAD_REQUEST)

        # Create Report record for admin moderation
        report = Report.objects.create(
            report_type=report_type,
            reason=reason,
            description=description,
            reporter=request.user,
            reported_user=reported_user,
            listing=listing_obj,
            message=message_obj,
            status='pending'
        )

        return Response({
            "message": "Report submitted successfully. Our moderation team will review this report shortly.",
            "report_id": str(report.id),
            "status": report.status,
            "created_at": report.created_at.isoformat()
        }, status=status.HTTP_201_CREATED)


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

    @swagger_auto_schema(
        request_body=BlockUserSerializer,
        responses={200: openapi.Response(description="User blocked successfully")}
    )
    @action(detail=False, methods=['post'], url_path='block')
    def block_user(self, request):
        view = BlockUserView.as_view()
        return view(request._request)

    @swagger_auto_schema(
        request_body=UnblockUserSerializer,
        responses={200: openapi.Response(description="User unblocked successfully")}
    )
    @action(detail=False, methods=['post'], url_path='unblock')
    def unblock_user(self, request):
        view = UnblockUserView.as_view()
        return view(request._request)

    @swagger_auto_schema(responses={200: BlockedUserItemSerializer(many=True)})
    @action(detail=False, methods=['get'], url_path='blocked')
    def blocked_users(self, request):
        view = BlockedUsersListView.as_view()
        return view(request._request)

    @swagger_auto_schema(
        request_body=SubmitReportSerializer,
        responses={201: openapi.Response(description="Report submitted successfully")}
    )
    @action(detail=False, methods=['post'], url_path='report')
    def submit_report(self, request):
        view = SubmitReportView.as_view()
        return view(request._request)

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

        # Enforce Apple Guideline 1.2 User Blocking Rules
        if BlockedUser.objects.filter(blocker=receiver, blocked=request.user).exists():
            return Response(
                {"error": "You have been blocked by this user and cannot send messages to them."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        if BlockedUser.objects.filter(blocker=request.user, blocked=receiver).exists():
            return Response(
                {"error": "You have blocked this user. Unblock them to send messages."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

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
            raw_data = MessageSerializer(message).data
            message_payload = json.loads(json.dumps(raw_data, cls=DjangoJSONEncoder))
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
            except Exception as e:
                logger.error("Failed to broadcast Pusher new_message in send: %s", str(e), exc_info=True)

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
            openapi.Parameter('identifier', openapi.IN_PATH, description="UUID of the chat partner or ChatRoom ID", type=openapi.TYPE_STRING),
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number for pagination", type=openapi.TYPE_INTEGER, required=False),
            openapi.Parameter('page_size', openapi.IN_QUERY, description="Number of messages per page (default: 50, max: 100)", type=openapi.TYPE_INTEGER, required=False),
            openapi.Parameter('limit', openapi.IN_QUERY, description="Limit number of messages returned", type=openapi.TYPE_INTEGER, required=False),
            openapi.Parameter('before', openapi.IN_QUERY, description="Message UUID cursor to fetch older messages before", type=openapi.TYPE_STRING, required=False),
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

        messages_qs = room.messages.all().select_related('sender', 'receiver', 'listing', 'chatroom').order_by('timestamp')

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

        # Check for pagination / cursor query params
        page_num = request.query_params.get('page')
        page_size = request.query_params.get('page_size') or request.query_params.get('limit')
        before_id = request.query_params.get('before') or request.query_params.get('before_id')

        if before_id:
            try:
                ref_msg = Message.objects.get(id=before_id)
                messages_qs = messages_qs.filter(timestamp__lt=ref_msg.timestamp)
            except Exception:
                pass

        if page_num or page_size or before_id:
            try:
                size = min(int(page_size), 100) if page_size else 50
            except (ValueError, TypeError):
                size = 50

            if page_num:
                try:
                    p = max(int(page_num), 1)
                except (ValueError, TypeError):
                    p = 1
                total = messages_qs.count()
                start = (p - 1) * size
                end = start + size
                paged_messages = list(messages_qs[start:end])
                serializer = MessageSerializer(paged_messages, many=True)
                return Response({
                    "count": total,
                    "page": p,
                    "page_size": size,
                    "has_next": end < total,
                    "has_previous": p > 1,
                    "results": serializer.data
                }, status=status.HTTP_200_OK)
            elif before_id or page_size:
                total = messages_qs.count()
                paged_messages = list(messages_qs.order_by('-timestamp')[:size])
                paged_messages.reverse()
                serializer = MessageSerializer(paged_messages, many=True)
                return Response({
                    "count": total,
                    "page_size": size,
                    "results": serializer.data
                }, status=status.HTTP_200_OK)

        serializer = MessageSerializer(messages_qs, many=True)
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

            is_blocked_by_me = BlockedUser.objects.filter(blocker=user, blocked=partner).exists()
            is_blocked_by_them = BlockedUser.objects.filter(blocker=partner, blocked=user).exists()
            is_blocked = is_blocked_by_me or is_blocked_by_them

            # Robust listing resolution so listing_title is never null if conversation began from a listing
            listing = room.listing
            if not listing and last_msg and last_msg.listing:
                listing = last_msg.listing
                room.listing = listing
                room.save(update_fields=['listing'])
            if not listing:
                msg_with_listing = room.messages.filter(listing__isnull=False).order_by('-timestamp').first()
                if msg_with_listing:
                    listing = msg_with_listing.listing
                    room.listing = listing
                    room.save(update_fields=['listing'])

            results.append({
                "chatroom_id": str(room.id),
                "channel_name": room.channel_name,
                "event": "new_message",
                "chat_partner": {
                    "id": str(partner.id),
                    "email": partner.email,
                    "full_name": partner.full_name or partner.email,
                    "role": partner.role,
                    "profile_picture": profile_pic,
                    "is_blocked": is_blocked,
                    "is_blocked_by_me": is_blocked_by_me
                },
                "last_message": last_msg.message if last_msg else "",
                "last_message_time": last_msg.timestamp.isoformat() if last_msg else room.created_at.isoformat(),
                "unread_count": unread_count,
                "listing_id": str(listing.id) if listing else None,
                "listing_title": listing.title if listing else None,
                "is_blocked": is_blocked
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

        # Enforce Apple Guideline 1.2 User Blocking Rules
        if BlockedUser.objects.filter(blocker=receiver, blocked=request.user).exists():
            return Response(
                {"error": "You have been blocked by this agent and cannot contact them."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        if BlockedUser.objects.filter(blocker=request.user, blocked=receiver).exists():
            return Response(
                {"error": "You have blocked this agent. Unblock them to send inquiries."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

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
            raw_data = MessageSerializer(message).data
            message_payload = json.loads(json.dumps(raw_data, cls=DjangoJSONEncoder))
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
            except Exception as e:
                logger.error("Failed to broadcast Pusher new_message in contact_agent: %s", str(e), exc_info=True)

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
