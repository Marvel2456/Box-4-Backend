from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Listing, ListingImage
from .serializers import ListingSerializer
from profiles.models import AgentProfile

class IsAgentOwnerOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.role in ['agent', 'admin']

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.role == 'admin':
            return True
        return obj.agent == request.user


class ListingViewSet(viewsets.ModelViewSet):
    queryset = Listing.objects.all().order_by('-created_at')
    serializer_class = ListingSerializer
    permission_classes = [IsAgentOwnerOrReadOnly]

    def update(self, request, *args, **kwargs):
        # Override to support partial updates on both PUT and PATCH requests
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def boost(self, request, pk=None):
        listing = self.get_object()
        
        # Verify ownership
        if listing.agent != request.user and request.user.role != 'admin':
            return Response({"error": "You do not have permission to manage this listing."}, status=status.HTTP_403_FORBIDDEN)
            
        # Toggle off is always allowed
        if listing.is_boosted:
            listing.is_boosted = False
            listing.save()
            return Response({
                "message": "Listing unboosted successfully.",
                "is_boosted": listing.is_boosted
            }, status=status.HTTP_200_OK)

        # Toggle on requires plan check
        try:
            profile = listing.agent.agent_profile
        except AgentProfile.DoesNotExist:
            return Response({"error": "Agent profile not found."}, status=status.HTTP_400_BAD_REQUEST)

        plan = profile.plan
        if not plan:
            return Response({"error": "No active subscription plan found. Please subscribe to boost listings."}, status=status.HTTP_403_FORBIDDEN)

        current_boosted_count = Listing.objects.filter(agent=listing.agent, is_boosted=True).count()
        if current_boosted_count >= plan.max_boosted:
            return Response({
                "error": f"You have reached your plan limit of {plan.max_boosted} boosted listings on the '{plan.name}' plan. Please upgrade to boost more."
            }, status=status.HTTP_403_FORBIDDEN)

        listing.is_boosted = True
        listing.save()
        return Response({
            "message": "Listing boosted successfully!",
            "is_boosted": listing.is_boosted
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def feature(self, request, pk=None):
        listing = self.get_object()
        
        # Verify ownership
        if listing.agent != request.user and request.user.role != 'admin':
            return Response({"error": "You do not have permission to manage this listing."}, status=status.HTTP_403_FORBIDDEN)

        # Toggle off is always allowed
        if listing.is_featured:
            listing.is_featured = False
            listing.save()
            return Response({
                "message": "Listing removed from featured list successfully.",
                "is_featured": listing.is_featured
            }, status=status.HTTP_200_OK)

        # Toggle on requires plan check
        try:
            profile = listing.agent.agent_profile
        except AgentProfile.DoesNotExist:
            return Response({"error": "Agent profile not found."}, status=status.HTTP_400_BAD_REQUEST)

        plan = profile.plan
        if not plan:
            return Response({"error": "No active subscription plan found. Please subscribe to feature listings."}, status=status.HTTP_403_FORBIDDEN)

        current_featured_count = Listing.objects.filter(agent=listing.agent, is_featured=True).count()
        if current_featured_count >= plan.max_featured:
            return Response({
                "error": f"You have reached your plan limit of {plan.max_featured} featured listings on the '{plan.name}' plan. Please upgrade to feature more."
            }, status=status.HTTP_403_FORBIDDEN)

        listing.is_featured = True
        listing.save()
        return Response({
            "message": "Listing featured successfully!",
            "is_featured": listing.is_featured
        }, status=status.HTTP_200_OK)
