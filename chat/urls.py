from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ChatViewSet, 
    ContactAgentView, 
    PusherAuthView,
    BlockUserView,
    UnblockUserView,
    BlockedUsersListView,
    SubmitReportView
)

router = DefaultRouter()
router.register(r'messages', ChatViewSet, basename='chat-messages')

urlpatterns = [
    path('pusher/auth/', PusherAuthView.as_view(), name='pusher-auth'),
    path('contact-agent/', ContactAgentView.as_view(), name='contact-agent'),
    path('users/block/', BlockUserView.as_view(), name='chat-user-block'),
    path('users/unblock/', UnblockUserView.as_view(), name='chat-user-unblock'),
    path('users/blocked/', BlockedUsersListView.as_view(), name='chat-users-blocked'),
    path('report/', SubmitReportView.as_view(), name='chat-submit-report'),
    path('', include(router.urls)),
]
