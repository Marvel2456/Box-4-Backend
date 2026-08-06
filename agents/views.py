from rest_framework import permissions, status, generics
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Listing, ListingImage
from .serializers import (
    ListingSerializer, 
    ListingImageUploadSerializer, 
    ListingImageSerializer,
    AgentDashboardResponseSerializer
)
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
    serializer_class = ListingSerializer
    permission_classes = [IsAgentOwnerOrReadOnly]

    def get_queryset(self):
        queryset = Listing.objects.all().order_by('-created_at')

        # Filter by Tab Type (All, Luxury, Residential, Commercial)
        tab_type = self.request.query_params.get('type') or self.request.query_params.get('tab')
        if tab_type:
            tab_type = tab_type.lower()
            if tab_type == 'luxury':
                queryset = queryset.filter(Q(is_featured=True) | Q(category__in=['villa', 'duplex', 'mansion']) | Q(price__gte=15000000))
            elif tab_type == 'residential':
                queryset = queryset.filter(category__in=['house', 'apartment', 'villa', 'condo', 'bungalow', 'duplex', 'single_flat', 'lodge', 'airbnb'])
            elif tab_type == 'commercial':
                queryset = queryset.filter(category__in=['mall', 'shop', 'plaza', 'multi_story_building', 'hotel', 'land'])

        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(address__icontains=search) |
                Q(category__icontains=search)
            )

        return queryset


class AgentDashboardView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AgentDashboardResponseSerializer

    @swagger_auto_schema(
        operation_description="Get Agent Home Dashboard Overview (Greeting, Active Listings metric, New Inquiries metric, Subscription details, Total Views metric, and recent active listings list).",
        responses={200: AgentDashboardResponseSerializer}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        display_name = user.full_name or user.email.split('@')[0]

        # 1. Profile Picture & Subscription
        profile_picture = None
        plan_name = "Free"
        days_left = 30
        try:
            if hasattr(user, 'agent_profile') and user.agent_profile:
                profile = user.agent_profile
                if profile.profile_picture:
                    profile_picture = request.build_absolute_uri(profile.profile_picture.url)
                if profile.plan:
                    plan_name = profile.plan.name
        except Exception:
            pass

        # 2. Agent Listings
        user_listings = Listing.objects.filter(agent=user)
        active_listings_qs = user_listings.filter(status='active')
        active_count = active_listings_qs.count()

        # Listings added this week
        one_week_ago = timezone.now() - timedelta(days=7)
        this_week_count = active_listings_qs.filter(created_at__gte=one_week_ago).count()

        # 3. New Inquiries (Messages received for user's listings)
        from chat.models import Message
        new_inquiries_count = Message.objects.filter(receiver=user).count()

        # 4. Total Views across all agent's listings
        total_views = user_listings.aggregate(total=Sum('views_count'))['total'] or 0

        metrics = {
            "active_listings": {
                "count": active_count,
                "note": f"{this_week_count} This week"
            },
            "new_inquiries": {
                "count": new_inquiries_count,
                "note": "Total inquiries"
            },
            "subscription": {
                "plan_name": plan_name,
                "days_left": days_left,
                "days_left_text": f"{days_left} Days left"
            },
            "views": {
                "total_views": total_views,
                "trend": "-3"
            }
        }

        # Recent active listings for dashboard
        active_listings_data = ListingSerializer(active_listings_qs.order_by('-created_at')[:10], many=True, context={'request': request}).data

        return Response({
            "greeting": f"Hey, {display_name}!",
            "agent": {
                "id": str(user.id),
                "full_name": user.full_name,
                "email": user.email,
                "profile_picture": profile_picture
            },
            "metrics": metrics,
            "active_listings": active_listings_data
        }, status=status.HTTP_200_OK)


class AgentMyListingsView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ListingSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Listing.objects.filter(agent=user).order_by('-created_at')

        # Filter by Tab Type (All, Luxury, Residential, Commercial)
        tab_type = self.request.query_params.get('type') or self.request.query_params.get('tab')
        if tab_type:
            tab_type = tab_type.lower()
            if tab_type == 'luxury':
                queryset = queryset.filter(Q(is_featured=True) | Q(category__in=['villa', 'duplex', 'mansion']) | Q(price__gte=15000000))
            elif tab_type == 'residential':
                queryset = queryset.filter(category__in=['house', 'apartment', 'villa', 'condo', 'bungalow', 'duplex', 'single_flat', 'lodge', 'airbnb'])
            elif tab_type == 'commercial':
                queryset = queryset.filter(category__in=['mall', 'shop', 'plaza', 'multi_story_building', 'hotel', 'land'])

        # Search filter
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(address__icontains=search) |
                Q(category__icontains=search)
            )

        return queryset

    @swagger_auto_schema(
        operation_description="Get Agent My Listings management list (Screen 2). Supports tab filter (?type=all|luxury|residential|commercial) and search (?search=apartment).",
        responses={200: ListingSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


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
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = ListingImageUploadSerializer

    @swagger_auto_schema(
        operation_description="Upload property photos (Step 2 flow). Auto-converts photos to WebP format.",
        manual_parameters=[
            openapi.Parameter(
                name='images',
                in_=openapi.IN_FORM,
                description='Property photo file to upload.',
                type=openapi.TYPE_FILE,
                required=False
            ),
            openapi.Parameter(
                name='image',
                in_=openapi.IN_FORM,
                description='Single property photo file to upload.',
                type=openapi.TYPE_FILE,
                required=False
            ),
            openapi.Parameter(
                name='listing_id',
                in_=openapi.IN_FORM,
                description='Optional UUID of an existing listing to attach photos to.',
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        consumes=['multipart/form-data'],
        responses={201: ListingImageSerializer(many=True)}
    )
    def post(self, request, *args, **kwargs):
        images = request.FILES.getlist('images')
        single_image = request.FILES.get('image')
        if single_image and single_image not in images:
            images.append(single_image)

        if not images:
            return Response({"error": "At least one image file must be provided under 'images' or 'image'."}, status=status.HTTP_400_BAD_REQUEST)

        listing_id = request.data.get('listing_id')
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
