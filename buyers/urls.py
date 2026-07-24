from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BuyerPropertyViewSet, AgentViewSet, SavedListingViewSet

router = DefaultRouter()
router.register(r'properties', BuyerPropertyViewSet, basename='buyer-properties')
router.register(r'agents', AgentViewSet, basename='buyer-agents')
router.register(r'saved', SavedListingViewSet, basename='buyer-saved')

urlpatterns = [
    path('', include(router.urls)),
]
