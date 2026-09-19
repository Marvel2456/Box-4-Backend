from django.urls import path
from .views import (
    ListingListCreateView,
    ListingDetailView,
    ListingBoostView,
    ListingFeatureView,
    ListingUploadPhotosView,
    ListingDeletePhotoView,
    AgentDashboardView,
    AgentMyListingsView,
    AgentProfileDetailView,
    CategoryListView,
    TagListView,
    AgentKYCVerifyView,
    AgentKYCStatusView,
)
from .subscription_views import (
    AgentPlanListView,
    AgentBoostPlanListView,
    AgentCurrentSubscriptionView,
    AgentSubscribeView,
    AgentCancelSubscriptionView,
    AgentSubscriptionHistoryView,
)

urlpatterns = [
    # KYC
    path('kyc/verify/', AgentKYCVerifyView.as_view(), name='agent-kyc-verify'),
    path('kyc/status/', AgentKYCStatusView.as_view(), name='agent-kyc-status'),

    # Taxonomies & Profiles
    path('categories/', CategoryListView.as_view(), name='agent-categories'),
    path('tags/', TagListView.as_view(), name='agent-tags'),
    path('profile/', AgentProfileDetailView.as_view(), name='agent-profile'),
    path('dashboard/', AgentDashboardView.as_view(), name='agent-dashboard'),

    # Subscription Plans & Pay-As-You-Boost Packages
    path('plans/', AgentPlanListView.as_view(), name='agent-plans-list'),
    path('subscription/plans/', AgentPlanListView.as_view(), name='agent-subscription-plans-list'),
    path('boost-plans/', AgentBoostPlanListView.as_view(), name='agent-boost-plans-list'),
    path('properties/boost-plans/', AgentBoostPlanListView.as_view(), name='agent-properties-boost-plans-list'),

    # Agent Subscription Flow
    path('subscription/', AgentCurrentSubscriptionView.as_view(), name='agent-subscription-status'),
    path('subscription/subscribe/', AgentSubscribeView.as_view(), name='agent-subscription-subscribe'),
    path('subscription/cancel/', AgentCancelSubscriptionView.as_view(), name='agent-subscription-cancel'),
    path('subscription/history/', AgentSubscriptionHistoryView.as_view(), name='agent-subscription-history'),

    # Property Listings Management & Media
    path('properties/', ListingListCreateView.as_view(), name='listing-list'),
    path('properties/my-listings/', AgentMyListingsView.as_view(), name='agent-my-listings'),
    path('properties/upload-photos/', ListingUploadPhotosView.as_view(), name='listing-upload-photos'),
    path('properties/images/<uuid:image_id>/', ListingDeletePhotoView.as_view(), name='listing-delete-photo'),
    path('properties/<uuid:pk>/', ListingDetailView.as_view(), name='listing-detail'),
    path('properties/<uuid:pk>/boost/', ListingBoostView.as_view(), name='listing-boost'),
    path('properties/<uuid:pk>/feature/', ListingFeatureView.as_view(), name='listing-feature'),
]
