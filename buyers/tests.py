from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from agents.models import Listing, Category, Tag
from profiles.models import Plan, AgentProfile
from .models import SavedListing

User = get_user_model()

class BuyerAPITests(APITestCase):
    def setUp(self):
        # 1. Create a Plan & subscribed Agent
        self.plan = Plan.objects.create(name="Gold", price=19.99, max_boosted=5, max_featured=2)
        
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

        # 3. Create Categories and Tags
        self.cat_duplex = Category.objects.create(name="Duplex")
        self.cat_apartment = Category.objects.create(name="Apartment")
        self.cat_villa = Category.objects.create(name="Villa")

        self.tag_luxury = Tag.objects.create(name="Luxury")
        self.tag_waterfront = Tag.objects.create(name="Waterfront")

        # 4. Create properties at different geographic coordinates:
        # Listing A: Lekki (6.4281, 3.4219)
        self.listing_a = Listing.objects.create(
            agent=self.agent_user,
            title="Lekki Duplex",
            category=self.cat_duplex,
            price=25000000.00,
            address="Admiralty Way, Lekki",
            city="Lekki",
            state="Lagos",
            latitude=6.428100,
            longitude=3.421900,
            is_published=True,
            is_boosted=True
        )
        self.listing_a.tag.add(self.tag_luxury, self.tag_waterfront)

        # Listing B: Yaba (6.5244, 3.3792) (~ 15 km away from Lekki)
        self.listing_b = Listing.objects.create(
            agent=self.agent_user,
            title="Yaba Apartment",
            category=self.cat_apartment,
            price=12000000.00,
            address="Herbert Macaulay Way, Yaba",
            city="Yaba",
            state="Lagos",
            latitude=6.524400,
            longitude=3.379200,
            is_published=True
        )

        # Listing C: Abuja (9.0765, 7.3986) (hundreds of km away)
        self.listing_c = Listing.objects.create(
            agent=self.agent_user,
            title="Abuja Mansion",
            category=self.cat_villa,
            price=80000000.00,
            address="Maitama, Abuja",
            city="Maitama",
            state="Abuja",
            latitude=9.076500,
            longitude=7.398600,
            is_published=True
        )
        self.listing_c.tag.add(self.tag_luxury)

        # Endpoints
        self.search_url = reverse('buyer-properties-list')
        self.top_url = reverse('buyer-properties-top')
        self.agents_url = reverse('buyer-agents-list')
        self.saved_url = reverse('buyer-saved-list')

    def get_jwt_token(self, email, password):
        response = self.client.post(reverse('auth_login'), {"email": email, "password": password})
        return response.data['access']

    def test_search_and_multi_filters(self):
        token = self.get_jwt_token("buyer@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 1. Search by Keyword across title/city/category/tag
        res = self.client.get(self.search_url, {"search": "Lekki"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data['results']), 1)
        self.assertEqual(res.data['results'][0]['title'], "Lekki Duplex")

        # Search by tag keyword
        res_tag = self.client.get(self.search_url, {"search": "Luxury"})
        self.assertEqual(res_tag.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_tag.data['results']), 2)

        # 2. Filter by Category
        res_cat = self.client.get(self.search_url, {"category": "Duplex"})
        self.assertEqual(res_cat.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_cat.data['results']), 1)
        self.assertEqual(res_cat.data['results'][0]['title'], "Lekki Duplex")

        # 3. Filter by Tag
        res_tag_filter = self.client.get(self.search_url, {"tag": "Waterfront"})
        self.assertEqual(res_tag_filter.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_tag_filter.data['results']), 1)
        self.assertEqual(res_tag_filter.data['results'][0]['title'], "Lekki Duplex")

        # 4. Filter by State and City
        res_loc = self.client.get(self.search_url, {"state": "Lagos", "city": "Yaba"})
        self.assertEqual(res_loc.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_loc.data['results']), 1)
        self.assertEqual(res_loc.data['results'][0]['title'], "Yaba Apartment")

        # 5. Buyers Category & Tag list endpoints
        cat_res = self.client.get(reverse('buyer-categories'))
        self.assertEqual(cat_res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(cat_res.data), 3)

        tag_res = self.client.get(reverse('buyer-tags'))
        self.assertEqual(tag_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(tag_res.data), 2)

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
        self.assertNotIn('listings', results[0])

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

        # 1. Save listing -> should return full listing details and is_saved=True
        response = self.client.post(self.saved_url, {"listing_id": self.listing_a.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data.get('is_saved'))
        self.assertIn('listing', response.data)
        self.assertEqual(response.data['listing']['id'], str(self.listing_a.id))
        self.assertEqual(response.data['listing']['title'], "Lekki Duplex")
        self.assertTrue(SavedListing.objects.filter(buyer=self.buyer_user, listing=self.listing_a).exists())

        # 2. Toggle unsave by posting the same listing_id again -> should unsave and return is_saved=False
        toggle_response = self.client.post(self.saved_url, {"listing_id": self.listing_a.id})
        self.assertEqual(toggle_response.status_code, status.HTTP_200_OK)
        self.assertFalse(toggle_response.data.get('is_saved'))
        self.assertEqual(toggle_response.data.get('listing_id'), str(self.listing_a.id))
        self.assertFalse(SavedListing.objects.filter(buyer=self.buyer_user, listing=self.listing_a).exists())

        # 3. Save it again
        re_save_response = self.client.post(self.saved_url, {"listing_id": self.listing_a.id})
        self.assertEqual(re_save_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(re_save_response.data.get('is_saved'))
        self.assertTrue(SavedListing.objects.filter(buyer=self.buyer_user, listing=self.listing_a).exists())

        # 4. View saved listings
        get_response = self.client.get(self.saved_url)
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        saved = get_response.data['results']
        self.assertEqual(len(saved), 1)

        # 5. Remove listing from saved (using DELETE on property listing UUID)
        delete_url = reverse('buyer-saved-detail', kwargs={'pk': self.listing_a.id})
        del_response = self.client.delete(delete_url)
        self.assertEqual(del_response.status_code, status.HTTP_200_OK)
        self.assertFalse(SavedListing.objects.filter(buyer=self.buyer_user, listing=self.listing_a).exists())

    def test_buyer_profile_endpoint(self):
        token = self.get_jwt_token("buyer@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        profile_url = reverse('buyer-profile')
        get_res = self.client.get(profile_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)

        update_res = self.client.patch(profile_url, {
            "city": "Lagos",
            "bio": "Looking for modern apartments.",
            "profile_picture": "https://box4realestate.cloud/media/profiles/avatar1.webp"
        }, format='json')
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)
        self.assertEqual(update_res.data['city'], "Lagos")
        self.assertIsNotNone(update_res.data['profile_picture'])

    def test_buyer_dashboard_endpoint(self):
        token = self.get_jwt_token("buyer@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Update buyer location coordinates and profile picture
        profile_url = reverse('buyer-profile')
        self.client.patch(profile_url, {
            "latitude": 6.5244,
            "longitude": 3.3792,
            "city": "Lagos",
            "profile_picture": "https://box4realestate.cloud/media/profiles/buyer_avatar.webp"
        }, format='json')

        dashboard_url = reverse('buyer-dashboard')
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user_location', response.data)
        self.assertIn('profile_picture', response.data)
        self.assertIn('profile_picture', response.data['user_location'])
        self.assertIn('nearest_properties', response.data)
        self.assertIn('top_agents', response.data)
        self.assertIn('top_locations', response.data)
        self.assertIsNotNone(response.data['user_location']['latitude'])
        self.assertIsNotNone(response.data['user_location']['profile_picture'])

    def test_search_agents_by_keyword_and_location(self):
        # Create second agent in Abuja
        agent2 = User.objects.create_user(
            email="abuja_agent@example.com",
            username="abuja_agent@example.com",
            password="securepassword123",
            full_name="Abuja Prime Realtor",
            role="agent"
        )
        agent2.agent_profile.agency_name = "Capital Prime Properties"
        agent2.agent_profile.city = "Abuja"
        agent2.agent_profile.state = "FCT"
        agent2.agent_profile.country = "Nigeria"
        agent2.agent_profile.rating = 4.9
        agent2.agent_profile.is_verified = True
        agent2.agent_profile.latitude = 9.076500
        agent2.agent_profile.longitude = 7.398600
        agent2.agent_profile.save()

        search_url = reverse('buyer-agent-search')

        # 1. Search by keyword matching agency name
        res = self.client.get(search_url, {'search': 'Capital Prime'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data['results'] if 'results' in res.data else res.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['email'], "abuja_agent@example.com")
        self.assertEqual(results[0]['agency_name'], "Capital Prime Properties")

        # 2. Search by city filter
        res_city = self.client.get(search_url, {'city': 'Abuja'})
        self.assertEqual(res_city.status_code, status.HTTP_200_OK)
        city_results = res_city.data['results'] if 'results' in res_city.data else res_city.data
        self.assertEqual(len(city_results), 1)
        self.assertEqual(city_results[0]['city'], "Abuja")

    def test_search_agents_by_verification_and_min_rating(self):
        # Create unverified agent with lower rating
        unverified_agent = User.objects.create_user(
            email="newbie@example.com",
            username="newbie@example.com",
            password="securepassword123",
            full_name="Newbie Agent",
            role="agent"
        )
        unverified_agent.agent_profile.rating = 2.5
        unverified_agent.agent_profile.is_verified = False
        unverified_agent.agent_profile.save()

        search_url = reverse('buyer-agent-search')

        # Filter only verified agents
        res_ver = self.client.get(search_url, {'is_verified': 'true'})
        self.assertEqual(res_ver.status_code, status.HTTP_200_OK)
        ver_results = res_ver.data['results'] if 'results' in res_ver.data else res_ver.data
        for agent in ver_results:
            self.assertTrue(agent['is_verified'])

        # Filter by min_rating 4.0
        res_rating = self.client.get(search_url, {'min_rating': '4.0'})
        self.assertEqual(res_rating.status_code, status.HTTP_200_OK)
        rating_results = res_rating.data['results'] if 'results' in res_rating.data else res_rating.data
        for agent in rating_results:
            self.assertGreaterEqual(agent['rating'], 4.0)

    def test_search_agents_response_does_not_contain_coordinates_or_license_number(self):
        search_url = reverse('buyer-agent-search')
        res = self.client.get(search_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data['results'] if 'results' in res.data else res.data
        self.assertGreaterEqual(len(results), 1)
        first_agent = results[0]

        # Verify excluded fields
        self.assertNotIn('latitude', first_agent)
        self.assertNotIn('longitude', first_agent)
        self.assertNotIn('license_number', first_agent)

        # Verify expected fields
        self.assertIn('id', first_agent)
        self.assertIn('full_name', first_agent)
        self.assertIn('email', first_agent)
        self.assertIn('agency_name', first_agent)
        self.assertIn('is_verified', first_agent)
        self.assertIn('rating', first_agent)
        self.assertIn('total_listings_count', first_agent)

    def test_search_agents_proximity_and_sorting(self):
        # Set agent location in Lekki (6.4281, 3.4219)
        self.agent_user.agent_profile.latitude = 6.428100
        self.agent_user.agent_profile.longitude = 3.421900
        self.agent_user.agent_profile.city = "Lekki"
        self.agent_user.agent_profile.save()

        # Buyer coordinates in Victoria Island (6.4253, 3.4219) (~ 0.3 km away)
        search_url = reverse('buyer-agent-search')
        res = self.client.get(search_url, {
            'lat': 6.4253,
            'lng': 3.4219,
            'sort_by': 'nearest'
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data['results'] if 'results' in res.data else res.data
        self.assertGreaterEqual(len(results), 1)
        self.assertIsNotNone(results[0]['distance_km'])
        self.assertNotIn('latitude', results[0])
        self.assertNotIn('longitude', results[0])

    def test_buyer_record_listing_view_and_deduplication(self):
        token = self.get_jwt_token("buyer@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        from buyers.models import ListingView

        # Initial state: 0 views
        self.assertEqual(self.listing_a.views_count, 0)
        self.assertEqual(ListingView.objects.filter(listing=self.listing_a).count(), 0)

        view_url = reverse('buyer-record-view')

        # 1. First View -> Should create view instance and increment views_count
        res1 = self.client.post(view_url, {"listing_id": str(self.listing_a.id)})
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res1.data['created'])
        self.assertEqual(res1.data['views_count'], 1)
        self.listing_a.refresh_from_db()
        self.assertEqual(self.listing_a.views_count, 1)
        self.assertEqual(ListingView.objects.filter(buyer=self.buyer_user, listing=self.listing_a).count(), 1)

        # 2. Duplicate View -> Same buyer requests again -> Should NOT duplicate or increment count
        res2 = self.client.post(view_url, {"listing_id": str(self.listing_a.id)})
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertFalse(res2.data['created'])
        self.assertEqual(res2.data['views_count'], 1)
        self.listing_a.refresh_from_db()
        self.assertEqual(self.listing_a.views_count, 1)
        self.assertEqual(ListingView.objects.filter(buyer=self.buyer_user, listing=self.listing_a).count(), 1)

        # 3. Test alternate route 'properties/view/'
        alt_view_url = reverse('buyer-property-view')
        res3 = self.client.post(alt_view_url, {"id": str(self.listing_b.id)})
        self.assertEqual(res3.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res3.data['created'])
        self.assertEqual(res3.data['views_count'], 1)
        self.listing_b.refresh_from_db()
        self.assertEqual(self.listing_b.views_count, 1)
