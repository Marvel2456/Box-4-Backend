from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChatViewSet, ContactAgentView, PusherAuthView

router = DefaultRouter()
router.register(r'messages', ChatViewSet, basename='chat-messages')

urlpatterns = [
    path('pusher/auth/', PusherAuthView.as_view(), name='pusher-auth'),
    path('contact-agent/', ContactAgentView.as_view(), name='contact-agent'),
    path('', include(router.urls)),
]
