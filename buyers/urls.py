from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BuyerPropertyViewSet, AgentViewSet, SavedListingViewSet, BuyerProfileDetailView

router = DefaultRouter()
router.register(r'properties', BuyerPropertyViewSet, basename='buyer-properties')
router.register(r'agents', AgentViewSet, basename='buyer-agents')
router.register(r'saved', SavedListingViewSet, basename='buyer-saved')

urlpatterns = [
    path('profile/', BuyerProfileDetailView.as_view(), name='buyer-profile'),
    path('', include(router.urls)),
]
