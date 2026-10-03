from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, DeviceTokenView

router = DefaultRouter()
router.register(r'', NotificationViewSet, basename='notifications')

urlpatterns = [
    path('devices/', DeviceTokenView.as_view(), name='device-tokens'),
    path('', include(router.urls)),
]
