from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import BuyerProfile, AgentProfile, AdminProfile
from .serializers import (
    BuyerProfileSerializer, AgentProfileSerializer, AdminProfileSerializer,
    BuyerProfileOnboardingSerializer, AgentProfileOnboardingSerializer, AdminProfileOnboardingSerializer
)

class ProfileDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = BuyerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if not self.request or not self.request.user or self.request.user.is_anonymous:
            return BuyerProfileSerializer
        role = self.request.user.role
        if role == 'buyer':
            return BuyerProfileSerializer
        elif role == 'agent':
            return AgentProfileSerializer
        return AdminProfileSerializer

    def get_object(self):
        if not self.request or not self.request.user or self.request.user.is_anonymous:
            return None
        role = self.request.user.role
        if role == 'buyer':
            profile, _ = BuyerProfile.objects.get_or_create(user=self.request.user)
            return profile
        elif role == 'agent':
            profile, _ = AgentProfile.objects.get_or_create(user=self.request.user)
            return profile
        else:
            profile, _ = AdminProfile.objects.get_or_create(user=self.request.user)
            return profile

    def update(self, request, *args, **kwargs):
        # Override to force partial updates on both PUT and PATCH requests
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class ProfileOnboardingView(generics.UpdateAPIView):
    serializer_class = BuyerProfileOnboardingSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if not self.request or not self.request.user or self.request.user.is_anonymous:
            return BuyerProfileOnboardingSerializer
        role = self.request.user.role
        if role == 'buyer':
            return BuyerProfileOnboardingSerializer
        elif role == 'agent':
            return AgentProfileOnboardingSerializer
        return AdminProfileOnboardingSerializer

    def get_object(self):
        if not self.request or not self.request.user or self.request.user.is_anonymous:
            return None
        role = self.request.user.role
        if role == 'buyer':
            profile, _ = BuyerProfile.objects.get_or_create(user=self.request.user)
            return profile
        elif role == 'agent':
            profile, _ = AgentProfile.objects.get_or_create(user=self.request.user)
            return profile
        else:
            profile, _ = AdminProfile.objects.get_or_create(user=self.request.user)
            return profile

    def update(self, request, *args, **kwargs):
        # Override to force partial updates on both PUT and PATCH requests
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

