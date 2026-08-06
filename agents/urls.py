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
)

urlpatterns = [
    path('dashboard/', AgentDashboardView.as_view(), name='agent-dashboard'),
    path('properties/', ListingListCreateView.as_view(), name='listing-list'),
    path('properties/my-listings/', AgentMyListingsView.as_view(), name='agent-my-listings'),
    path('properties/upload-photos/', ListingUploadPhotosView.as_view(), name='listing-upload-photos'),
    path('properties/images/<uuid:image_id>/', ListingDeletePhotoView.as_view(), name='listing-delete-photo'),
    path('properties/<uuid:pk>/', ListingDetailView.as_view(), name='listing-detail'),
    path('properties/<uuid:pk>/boost/', ListingBoostView.as_view(), name='listing-boost'),
    path('properties/<uuid:pk>/feature/', ListingFeatureView.as_view(), name='listing-feature'),
]
