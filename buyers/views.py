from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Count, Avg
from django.contrib.auth import get_user_model
import math
from geopy.distance import geodesic

from drf_yasg.utils import swagger_auto_schema

from .models import SavedListing
from .serializers import (
    SavedListingSerializer, AgentDetailSerializer, BuyerDashboardSerializer
)
from agents.models import Listing
from agents.serializers import ListingSerializer
from profiles.models import BuyerProfile
from profiles.serializers import BuyerProfileSerializer

User = get_user_model()


class BuyerProfileDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BuyerProfileSerializer

    def get_object(self):
        profile, _ = BuyerProfile.objects.get_or_create(user=self.request.user)
        return profile

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


def haversine_distance(lat1, lon1, lat2, lon2):
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers
    return c * r


class BuyerPropertyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Listing.objects.filter(is_published=True)
    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request, *args, **kwargs):
        # 1. Apply basic query filters
        queryset = self.get_queryset()
        
        category = request.query_params.get('category')
        city = request.query_params.get('city')
        state = request.query_params.get('state')
        country = request.query_params.get('country')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        bedrooms = request.query_params.get('bedrooms')
        bathrooms = request.query_params.get('bathrooms')

        if category:
            queryset = queryset.filter(category=category)
        if city:
            queryset = queryset.filter(address__icontains=city)
        if state:
            queryset = queryset.filter(address__icontains=state)
        if country:
            queryset = queryset.filter(address__icontains=country)
        if min_price:
            queryset = queryset.filter(price__gte=min_price)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        if bedrooms:
            queryset = queryset.filter(bedrooms__gte=bedrooms)
        if bathrooms:
            queryset = queryset.filter(bathrooms__gte=bathrooms)

        # 2. Geolocation proximity filtering
        lat_param = request.query_params.get('latitude')
        lon_param = request.query_params.get('longitude')
        radius_param = request.query_params.get('radius_km', 10.0)

        # Calculate distances & filter
        results = []
        for listing in queryset:
            listing_data = ListingSerializer(listing, context={'request': request}).data
            
            if lat_param and lon_param:
                try:
                    dist = haversine_distance(lat_param, lon_param, listing.latitude, listing.longitude)
                    if dist > float(radius_param):
                        continue
                    listing_data['distance_km'] = round(dist, 2)
                except ValueError:
                    pass
            else:
                listing_data['distance_km'] = None
                
            results.append(listing_data)

        if lat_param and lon_param:
            results.sort(key=lambda x: x.get('distance_km', float('inf')))

        page = self.paginate_queryset(results)
        if page is not None:
            return self.get_paginated_response(page)

        return Response(results, status=status.HTTP_200_OK)

    @swagger_auto_schema(responses={200: ListingSerializer(many=True)})
    @action(detail=False, methods=['get'])
    def top(self, request):
        # Expose top listings / ads (boosted or featured), ranked by featured status then boosted status
        ads = Listing.objects.filter(
            Q(is_boosted=True) | Q(is_featured=True),
            is_published=True
        ).order_by('-is_featured', '-is_boosted', '-created_at')
        
        page = self.paginate_queryset(ads)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(ads, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AgentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(role='agent').order_by('-agent_profile__rating')
    serializer_class = AgentDetailSerializer
    permission_classes = [permissions.AllowAny]


class SavedListingViewSet(viewsets.ModelViewSet):
    serializer_class = SavedListingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SavedListing.objects.none()
        return SavedListing.objects.filter(buyer=self.request.user)

    def perform_create(self, serializer):
        saved_instance = serializer.save(buyer=self.request.user)
        agent = saved_instance.listing.agent
        if agent != self.request.user:
            from notifications.models import Notification
            Notification.objects.create(
                recipient=agent,
                sender=self.request.user,
                notification_type='saved_listing',
                title='Listing Saved',
                message=f"{self.request.user.full_name} saved your property listing '{saved_instance.listing.title}'.",
                listing=saved_instance.listing
            )

    def destroy(self, request, *args, **kwargs):
        # Allow deletion by saved listing pk or property listing uuid
        target_id = kwargs.get('pk')
        saved = SavedListing.objects.filter(buyer=request.user, listing_id=target_id).first()
        if not saved:
            saved = SavedListing.objects.filter(buyer=request.user, id=target_id).first()

        if not saved:
            return Response({"error": "Saved listing not found."}, status=status.HTTP_404_NOT_FOUND)

        saved.delete()
        return Response({"message": "Listing removed from saved properties successfully."}, status=status.HTTP_200_OK)


class BuyerDashboardView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BuyerDashboardSerializer

    @swagger_auto_schema(responses={200: BuyerDashboardSerializer()})
    def get(self, request, *args, **kwargs):
        user = request.user
        profile = getattr(user, 'buyer_profile', None)

        # 1. Determine buyer coordinates
        lat_param = request.query_params.get('lat') or request.query_params.get('latitude')
        lng_param = request.query_params.get('lng') or request.query_params.get('longitude')

        buyer_lat = None
        buyer_lng = None

        if lat_param and lng_param:
            try:
                buyer_lat = float(lat_param)
                buyer_lng = float(lng_param)
            except (ValueError, TypeError):
                pass

        if buyer_lat is None and profile and profile.latitude is not None and profile.longitude is not None:
            try:
                buyer_lat = float(profile.latitude)
                buyer_lng = float(profile.longitude)
            except (ValueError, TypeError):
                pass

        user_location_data = {
            "latitude": buyer_lat,
            "longitude": buyer_lng,
            "city": profile.city if profile else None,
            "state": profile.state if profile else None,
            "country": profile.country if profile else None,
        }

        # 2. Nearest 10 Properties via Geopy geodesic distance
        all_published_listings = Listing.objects.filter(is_published=True, status='active').prefetch_related('images', 'agent')
        
        nearest_properties_data = []

        if buyer_lat is not None and buyer_lng is not None:
            user_coords = (buyer_lat, buyer_lng)
            
            for listing in all_published_listings:
                listing_data = ListingSerializer(listing, context={'request': request}).data
                if listing.latitude is not None and listing.longitude is not None:
                    try:
                        listing_coords = (float(listing.latitude), float(listing.longitude))
                        dist_km = geodesic(user_coords, listing_coords).km
                        listing_data['distance_km'] = round(dist_km, 2)
                    except Exception:
                        listing_data['distance_km'] = None
                else:
                    listing_data['distance_km'] = None
                nearest_properties_data.append(listing_data)

            nearest_properties_data.sort(key=lambda x: (x.get('distance_km') is None, x.get('distance_km', float('inf'))))
            top_10_nearest = nearest_properties_data[:10]
        else:
            # Fallback if no user coordinates available
            latest_listings = all_published_listings.order_by('-created_at')[:10]
            top_10_nearest = []
            for listing in latest_listings:
                listing_data = ListingSerializer(listing, context={'request': request}).data
                listing_data['distance_km'] = None
                top_10_nearest.append(listing_data)

        # 3. Top 6 Selling / Active Agents
        top_agents_qs = User.objects.filter(role='agent')\
            .annotate(active_count=Count('listings', filter=Q(listings__is_published=True, listings__status='active')))\
            .order_by('-active_count', '-agent_profile__rating', '-date_joined')[:6]

        top_agents_data = AgentDetailSerializer(top_agents_qs, many=True, context={'request': request}).data

        # 4. Top Locations (Highest property density)
        raw_locations = Listing.objects.filter(is_published=True, status='active')\
            .values('address')\
            .annotate(listings_count=Count('id'), avg_price=Avg('price'))\
            .order_by('-listings_count')[:10]

        top_locations_data = []
        for item in raw_locations:
            addr = item['address']
            sample_listing = Listing.objects.filter(address=addr, is_published=True).first()
            cover_photo = None
            if sample_listing:
                sample_serialized = ListingSerializer(sample_listing, context={'request': request}).data
                cover_photo = sample_serialized.get('cover_photo')

            top_locations_data.append({
                "location": addr,
                "listings_count": item['listings_count'],
                "cover_photo": cover_photo,
                "avg_price": round(float(item['avg_price']), 2) if item['avg_price'] else 0.00
            })

        return Response({
            "user_location": user_location_data,
            "nearest_properties": top_10_nearest,
            "top_agents": top_agents_data,
            "top_locations": top_locations_data
        }, status=status.HTTP_200_OK)
