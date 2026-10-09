from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Notification, DeviceToken
from .serializers import (
    NotificationSerializer, 
    DeviceTokenSerializer, 
    DeviceTokenUnregisterSerializer
)

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        
        queryset = Notification.objects.filter(recipient=self.request.user).exclude(
            sender__is_deleted=True
        ).exclude(
            sender__is_active=False
        )
        
        notification_type = self.request.query_params.get('notification_type')
        is_read_param = self.request.query_params.get('is_read')

        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        if is_read_param is not None:
            if is_read_param.lower() in ['true', '1']:
                queryset = queryset.filter(is_read=True)
            elif is_read_param.lower() in ['false', '0']:
                queryset = queryset.filter(is_read=False)

        return queryset

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter('notification_type', openapi.IN_QUERY, description="Filter by type (message, saved_listing, inquiry, review, system)", type=openapi.TYPE_STRING),
            openapi.Parameter('is_read', openapi.IN_QUERY, description="Filter by read status (true / false)", type=openapi.TYPE_BOOLEAN),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = Notification.objects.filter(
            recipient=request.user, 
            is_read=False
        ).exclude(
            sender__is_deleted=True
        ).exclude(
            sender__is_active=False
        ).count()
        return Response({"unread_count": count}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'], url_path='read')
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='read-all')
    def read_all(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({"message": "All notifications marked as read."}, status=status.HTTP_200_OK)


class DeviceTokenView(generics.GenericAPIView):
    serializer_class = DeviceTokenSerializer
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        request_body=DeviceTokenSerializer,
        responses={200: DeviceTokenSerializer, 201: DeviceTokenSerializer}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        device_token = serializer.save()
        return Response(DeviceTokenSerializer(device_token).data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        request_body=DeviceTokenUnregisterSerializer,
        responses={200: openapi.Response(description="Device token deactivated successfully")}
    )
    def delete(self, request, *args, **kwargs):
        serializer = DeviceTokenUnregisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']
        DeviceToken.objects.filter(user=request.user, token=token).update(is_active=False)
        return Response({"message": "Device token deactivated successfully."}, status=status.HTTP_200_OK)
