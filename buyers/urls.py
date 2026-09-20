from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BuyerPropertyViewSet, AgentViewSet, AgentSearchView, SavedListingViewSet,
    BuyerProfileDetailView, BuyerDashboardView, ListingViewCreateView
)
from agents.views import CategoryListView, TagListView

router = DefaultRouter()
router.register(r'properties', BuyerPropertyViewSet, basename='buyer-properties')
router.register(r'agents', AgentViewSet, basename='buyer-agents')
router.register(r'saved', SavedListingViewSet, basename='buyer-saved')

urlpatterns = [
    path('views/', ListingViewCreateView.as_view(), name='buyer-record-view'),
    path('properties/view/', ListingViewCreateView.as_view(), name='buyer-property-view'),
    path('agents/search/', AgentSearchView.as_view(), name='buyer-agent-search'),
    path('dashboard/', BuyerDashboardView.as_view(), name='buyer-dashboard'),
    path('profile/', BuyerProfileDetailView.as_view(), name='buyer-profile'),
    path('categories/', CategoryListView.as_view(), name='buyer-categories'),
    path('tags/', TagListView.as_view(), name='buyer-tags'),
    path('', include(router.urls)),
]
