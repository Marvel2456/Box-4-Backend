from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.contrib.auth import get_user_model
import pusher
from django.conf import settings

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Message
from .serializers import (
    MessageSerializer, 
    InitiateChatSerializer, 
    SendMessageSerializer,
    ConversationPreviewSerializer,
    ContactAgentResponseSerializer
)
from agents.models import Listing

User = get_user_model()

class ChatViewSet(viewsets.GenericViewSet):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_pusher_client(self):
        if settings.PUSHER_APP_ID and settings.PUSHER_KEY and settings.PUSHER_SECRET:
            return pusher.Pusher(
                app_id=settings.PUSHER_APP_ID,
                key=settings.PUSHER_KEY,
                secret=settings.PUSHER_SECRET,
                cluster=settings.PUSHER_CLUSTER,
                ssl=True
            )
        return None

    @swagger_auto_schema(request_body=SendMessageSerializer, responses={201: MessageSerializer})
    @action(detail=False, methods=['post'])
    def send(self, request):
        receiver_id = request.data.get('receiver_id')
        msg_text = request.data.get('message')
        listing_id = request.data.get('listing_id')

        if not receiver_id or not msg_text:
            return Response({"error": "receiver_id and message are required fields."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            receiver = User.objects.get(id=receiver_id)
        except (User.DoesNotExist, ValueError):
            return Response({"error": "Receiver user not found."}, status=status.HTTP_404_NOT_FOUND)

        listing_obj = None
        if listing_id:
            listing_obj = Listing.objects.filter(id=listing_id).first()

        # Save message to database
        message = Message.objects.create(
            sender=request.user,
            receiver=receiver,
            listing=listing_obj,
            message=msg_text
        )

        # Create Notification
        if receiver != request.user:
            from notifications.models import Notification
            Notification.objects.create(
                recipient=receiver,
                sender=request.user,
                notification_type='message',
                title='New Message',
                message=f"{request.user.full_name}: {msg_text[:100]}",
                listing=listing_obj
            )

        # Broadcast Pusher Event
        pusher_client = self.get_pusher_client()
        if pusher_client:
            try:
                pusher_client.trigger(
                    f'private-chat_{receiver.id}',
                    'new_message',
                    {
                        'id': str(message.id),
                        'sender_id': str(request.user.id),
                        'sender_name': request.user.full_name,
                        'message': message.message,
                        'timestamp': message.timestamp.isoformat()
                    }
                )
            except Exception:
                pass

        serializer = MessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @swagger_auto_schema(
        responses={200: MessageSerializer(many=True)},
        manual_parameters=[
            openapi.Parameter('user_id', openapi.IN_PATH, description="UUID of the chat partner user", type=openapi.TYPE_STRING)
        ]
    )
    @action(detail=False, methods=['get'], url_path='history/(?P<user_id>[^/.]+)')
    def history(self, request, user_id=None):
        try:
            partner = User.objects.get(id=user_id)
        except (User.DoesNotExist, ValueError):
            return Response({"error": "Chat partner user not found."}, status=status.HTTP_404_NOT_FOUND)

        messages = Message.objects.filter(
            Q(sender=request.user, receiver=partner) | 
            Q(sender=partner, receiver=request.user)
        ).order_by('timestamp')

        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(responses={200: ConversationPreviewSerializer(many=True)})
    @action(detail=False, methods=['get'])
    def conversations(self, request):
        user = request.user
        messages = Message.objects.filter(Q(sender=user) | Q(receiver=user))

        partners = {}
        for msg in messages.order_by('-timestamp'):
            partner = msg.receiver if msg.sender == user else msg.sender
            if partner.id not in partners:
                profile_pic = None
                if hasattr(partner, 'agent_profile') and partner.agent_profile.profile_picture:
                    profile_pic = request.build_absolute_uri(partner.agent_profile.profile_picture.url)
                elif hasattr(partner, 'buyer_profile') and partner.buyer_profile.profile_picture:
                    profile_pic = request.build_absolute_uri(partner.buyer_profile.profile_picture.url)

                partners[partner.id] = {
                    "chat_partner": {
                        "id": str(partner.id),
                        "email": partner.email,
                        "full_name": partner.full_name,
                        "role": partner.role,
                        "profile_picture": profile_pic
                    },
                    "last_message": msg.message,
                    "last_message_time": msg.timestamp.isoformat()
                }

        return Response(list(partners.values()), status=status.HTTP_200_OK)


class ContactAgentView(generics.GenericAPIView):
    serializer_class = InitiateChatSerializer
    permission_classes = [permissions.IsAuthenticated]

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

        if receiver == request.user:
            return Response({"error": "You cannot initiate a chat conversation with yourself."}, status=status.HTTP_400_BAD_REQUEST)

        # Build initial message
        if custom_message and custom_message.strip():
            intro_msg = custom_message
        elif listing_obj:
            intro_msg = f"Hi {receiver.full_name}, I am interested in your property listing: '{listing_obj.title}' located at {listing_obj.address}."
        else:
            intro_msg = f"Hi {receiver.full_name}, I would like to connect with you regarding your property listings."

        # Save to database
        message = Message.objects.create(
            sender=request.user,
            receiver=receiver,
            listing=listing_obj,
            message=intro_msg
        )

        # Create Notification
        if receiver != request.user:
            from notifications.models import Notification
            Notification.objects.create(
                recipient=receiver,
                sender=request.user,
                notification_type='inquiry',
                title='Property Inquiry',
                message=intro_msg,
                listing=listing_obj
            )

        # Trigger Pusher
        if settings.PUSHER_APP_ID and settings.PUSHER_KEY and settings.PUSHER_SECRET:
            try:
                pusher_client = pusher.Pusher(
                    app_id=settings.PUSHER_APP_ID,
                    key=settings.PUSHER_KEY,
                    secret=settings.PUSHER_SECRET,
                    cluster=settings.PUSHER_CLUSTER,
                    ssl=True
                )
                pusher_client.trigger(
                    f'private-chat_{receiver.id}',
                    'new_message',
                    {
                        'id': str(message.id),
                        'sender_id': str(request.user.id),
                        'sender_name': request.user.full_name,
                        'message': message.message,
                        'timestamp': message.timestamp.isoformat()
                    }
                )
            except Exception:
                pass

        return Response({
            "message": "Chat conversation initiated successfully.",
            "chat_message": MessageSerializer(message).data
        }, status=status.HTTP_201_CREATED)
