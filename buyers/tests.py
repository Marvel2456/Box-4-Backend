from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from agents.models import Listing
from profiles.models import Plan, AgentProfile
from .models import SavedListing

User = get_user_model()

class BuyerAPITests(APITestCase):
    def setUp(self):
        # 1. Create a Plan & subscribed Agent
        self.plan = Plan.objects.create(name="Gold", price=19.99, max_listings=10)
        
        self.agent_user = User.objects.create_user(
            email="agent@example.com",
            username="agent@example.com",
            password="securepassword123",
            full_name="Premium Agent",
            role="agent"
        )
        self.agent_user.agent_profile.plan = self.plan
        self.agent_user.agent_profile.rating = 4.8
        self.agent_user.agent_profile.agency_name = "Real Homes Ltd"
        self.agent_user.agent_profile.save()

        # 2. Create Buyer user
        self.buyer_user = User.objects.create_user(
            email="buyer@example.com",
            username="buyer@example.com",
            password="securepassword123",
            full_name="Active Buyer",
            role="buyer"
        )
        self.buyer_user.is_email_verified = True
        self.buyer_user.save()

        # 3. Create properties at different geographic coordinates:
        # Listing A: Lekki (6.4281, 3.4219)
        self.listing_a = Listing.objects.create(
            agent=self.agent_user,
            title="Lekki Duplex",
            category="duplex",
            price=25000000.00,
            address="Admiralty Way, Lekki",
            latitude=6.428100,
            longitude=3.421900,
            is_published=True,
            is_boosted=True
        )

        # Listing B: Yaba (6.5244, 3.3792) (~ 15 km away from Lekki)
        self.listing_b = Listing.objects.create(
            agent=self.agent_user,
            title="Yaba Apartment",
            category="apartment",
            price=12000000.00,
            address="Herbert Macaulay Way, Yaba",
            latitude=6.524400,
            longitude=3.379200,
            is_published=True
        )

        # Listing C: Abuja (9.0765, 7.3986) (hundreds of km away)
        self.listing_c = Listing.objects.create(
            agent=self.agent_user,
            title="Abuja Mansion",
            category="villa",
            price=80000000.00,
            address="Maitama, Abuja",
            latitude=9.076500,
            longitude=7.398600,
            is_published=True
        )

        # Endpoints
        self.search_url = reverse('buyer-properties-list')
        self.top_url = reverse('buyer-properties-top')
        self.agents_url = reverse('buyer-agents-list')
        self.saved_url = reverse('buyer-saved-list')

    def get_jwt_token(self, email, password):
        response = self.client.post(reverse('auth_login'), {"email": email, "password": password})
        return response.data['access']

    def test_geolocation_radius_filter(self):
        token = self.get_jwt_token("buyer@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Query properties from Lekki (6.4281, 3.4219) with radius 20km
        # Should return Lekki Duplex first, then Yaba Apartment, but filter out Abuja Mansion.
        data = {
            "latitude": 6.428100,
            "longitude": 3.421900,
            "radius_km": 20.0
        }
        response = self.client.get(self.search_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = response.data['results']
        # Verify Listing C (Abuja) is excluded, leaving 2 items
        self.assertEqual(len(results), 2)
        
        # Verify ordering (closest first)
        self.assertEqual(results[0]['title'], "Lekki Duplex")
        self.assertEqual(results[1]['title'], "Yaba Apartment")
        self.assertIsNotNone(results[0]['distance_km'])

    def test_top_properties_ads(self):
        token = self.get_jwt_token("buyer@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Returns boosted/featured listings
        response = self.client.get(self.top_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], "Lekki Duplex")

    def test_top_agents_and_agent_detail(self):
        # 1. Top Agents list
        response = self.client.get(self.agents_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['full_name'], "Premium Agent")
        self.assertEqual(float(results[0]['rating']), 4.8)

        # 2. Agent Detail view
        detail_url = reverse('buyer-agents-detail', kwargs={'pk': self.agent_user.id})
        detail_res = self.client.get(detail_url)
        self.assertEqual(detail_res.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_res.data['full_name'], "Premium Agent")
        self.assertEqual(detail_res.data['agency_name'], "Real Homes Ltd")
        self.assertEqual(detail_res.data['total_listings_count'], 3)
        self.assertEqual(len(detail_res.data['listings']), 3)

    def test_saved_listings_lifecycle(self):
        token = self.get_jwt_token("buyer@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 1. Save listing
        response = self.client.post(self.saved_url, {"listing_id": self.listing_a.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(SavedListing.objects.filter(buyer=self.buyer_user, listing=self.listing_a).exists())

        # 2. Prevent saving duplicate
        dup_response = self.client.post(self.saved_url, {"listing_id": self.listing_a.id})
        self.assertEqual(dup_response.status_code, status.HTTP_400_BAD_REQUEST)

        # 3. View saved listings
        get_response = self.client.get(self.saved_url)
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        saved = get_response.data['results']
        self.assertEqual(len(saved), 1)

        # 4. Remove listing from saved (using property listing UUID)
        delete_url = reverse('buyer-saved-detail', kwargs={'pk': self.listing_a.id})
        del_response = self.client.delete(delete_url)
        self.assertEqual(del_response.status_code, status.HTTP_200_OK)
        self.assertFalse(SavedListing.objects.filter(buyer=self.buyer_user, listing=self.listing_a).exists())
