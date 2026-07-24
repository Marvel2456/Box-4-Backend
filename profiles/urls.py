from django.urls import path
from .views import ProfileDetailView, ProfileOnboardingView

urlpatterns = [
    path('my-profile/', ProfileDetailView.as_view(), name='my_profile'),
    path('onboard/', ProfileOnboardingView.as_view(), name='profile_onboard'),
]
