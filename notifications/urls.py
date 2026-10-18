from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, DeviceTokenView, TestPushNotificationView

router = DefaultRouter()
router.register(r'', NotificationViewSet, basename='notifications')

urlpatterns = [
    path('devices/', DeviceTokenView.as_view(), name='device-tokens'),
    path('test-push/', TestPushNotificationView.as_view(), name='notification-test-push'),
    path('devices/test/', TestPushNotificationView.as_view(), name='device-test-push'),
    path('', include(router.urls)),
]
