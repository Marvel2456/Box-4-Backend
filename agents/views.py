from rest_framework import permissions, status, generics
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from .models import Listing, ListingImage
from .serializers import ListingSerializer, ListingImageUploadSerializer, ListingImageSerializer
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


class ListingListCreateView(generics.ListCreateAPIView):
    queryset = Listing.objects.all().order_by('-created_at')
    serializer_class = ListingSerializer
    permission_classes = [IsAgentOwnerOrReadOnly]


class ListingDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer
    permission_classes = [IsAgentOwnerOrReadOnly]

    def update(self, request, *args, **kwargs):
        # Override to support partial updates on both PUT and PATCH requests
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class ListingBoostView(generics.GenericAPIView):
    queryset = Listing.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ListingSerializer

    @swagger_auto_schema(
        operation_description="Toggle boost status on a property listing.",
        responses={200: "Listing boosted / unboosted successfully."}
    )
    def post(self, request, pk, *args, **kwargs):
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


class ListingFeatureView(generics.GenericAPIView):
    queryset = Listing.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ListingSerializer

    @swagger_auto_schema(
        operation_description="Toggle feature status on a property listing.",
        responses={200: "Listing featured / unfeatured successfully."}
    )
    def post(self, request, pk, *args, **kwargs):
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


class ListingUploadPhotosView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ListingImageUploadSerializer

    @swagger_auto_schema(
        operation_description="Upload property photos (Step 2 flow). Auto-converts photos to WebP format.",
        request_body=ListingImageUploadSerializer,
        responses={201: "Photos uploaded successfully."}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        images = serializer.validated_data.get('images', [])
        single_image = serializer.validated_data.get('image')
        if single_image:
            images = list(images)
            images.append(single_image)

        listing_id = serializer.validated_data.get('listing_id')
        listing = None
        if listing_id:
            try:
                listing = Listing.objects.get(pk=listing_id)
            except Listing.DoesNotExist:
                return Response({"error": "Listing not found."}, status=status.HTTP_404_NOT_FOUND)

        created_image_objs = []
        for idx, img in enumerate(images):
            img_obj = ListingImage.objects.create(
                listing=listing,
                image=img,
                is_cover=(idx == 0 and listing is not None and listing.images.count() == 0)
            )
            created_image_objs.append(img_obj)

        output_serializer = ListingImageSerializer(created_image_objs, many=True, context={'request': request})
        return Response({
            "message": f"Successfully uploaded {len(created_image_objs)} photo(s).",
            "images": output_serializer.data
        }, status=status.HTTP_201_CREATED)


class ListingDeletePhotoView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = ListingImage.objects.all()
    serializer_class = ListingImageSerializer

    @swagger_auto_schema(
        operation_description="Delete a property photo by image ID (matches the delete 'x' button on photo cards).",
        responses={200: "Photo deleted successfully."}
    )
    def delete(self, request, image_id, *args, **kwargs):
        try:
            image_obj = ListingImage.objects.get(pk=image_id)
        except ListingImage.DoesNotExist:
            return Response({"error": "Photo not found."}, status=status.HTTP_404_NOT_FOUND)

        if image_obj.listing and image_obj.listing.agent != request.user and request.user.role != 'admin':
            return Response({"error": "You do not have permission to delete this photo."}, status=status.HTTP_403_FORBIDDEN)

        image_obj.delete()
        return Response({"message": "Photo deleted successfully.", "id": str(image_id)}, status=status.HTTP_200_OK)
