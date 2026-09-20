from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from profiles.models import Plan, AgentProfile
from .models import Listing, ListingImage

User = get_user_model()

class ListingAPITests(APITestCase):
    def setUp(self):
        # 1. Create a dynamic subscription plan
        self.silver_plan = Plan.objects.create(
            name="Silver",
            price=9.99,
            max_boosted=1,
            max_featured=1,
            max_images_per_listing=5
        )
        
        from agents.models import Category
        self.cat_house, _ = Category.objects.get_or_create(name="House")
        self.cat_apartment, _ = Category.objects.get_or_create(name="Apartment")
        self.cat_villa, _ = Category.objects.get_or_create(name="Villa")

        # 2. Create users
        self.agent_user = User.objects.create_user(
            email="agent1@example.com",
            username="agent1@example.com",
            password="securepassword123",
            full_name="Agent One",
            role="agent"
        )
        self.agent_user.is_email_verified = True
        self.agent_user.save()
        
        # Subscribe agent to plan and verify KYC for existing tests
        from profiles.models import AgentKYC
        self.agent_profile = self.agent_user.agent_profile
        self.agent_profile.plan = self.silver_plan
        self.agent_profile.is_verified = True
        self.agent_profile.save()
        self.agent_kyc, _ = AgentKYC.objects.get_or_create(agent_profile=self.agent_profile)
        self.agent_kyc.status = 'verified'
        self.agent_kyc.nin_verified = True
        self.agent_kyc.save()

        self.other_agent = User.objects.create_user(
            email="agent2@example.com",
            username="agent2@example.com",
            password="securepassword123",
            full_name="Agent Two",
            role="agent"
        )
        self.other_agent.is_email_verified = True
        self.other_agent.save()
        self.other_agent.agent_profile.plan = self.silver_plan
        self.other_agent.agent_profile.is_verified = True
        self.other_agent.agent_profile.save()
        other_kyc, _ = AgentKYC.objects.get_or_create(agent_profile=self.other_agent.agent_profile)
        other_kyc.status = 'verified'
        other_kyc.nin_verified = True
        other_kyc.save()

        self.buyer_user = User.objects.create_user(
            email="buyer1@example.com",
            username="buyer1@example.com",
            password="securepassword123",
            full_name="Buyer One",
            role="buyer"
        )
        self.buyer_user.is_email_verified = True
        self.buyer_user.save()

        # URLs
        self.list_url = reverse('listing-list')

    def get_jwt_token(self, email, password):
        response = self.client.post(reverse('auth_login'), {
            "email": email,
            "password": password
        })
        return response.data['access']

    def test_create_listing_success(self):
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        data = {
            "title": "Beautiful Villa",
            "category": "villa",
            "price": "15000000.00",
            "address": "Lekki, Lagos",
            "latitude": "6.428100",
            "longitude": "3.421900",
            "bedrooms": 4,
            "bathrooms": 4,
            "balconies": 2,
            "total_rooms": 10,
            "facilities": ["Parking lot", "Pool"]
        }
        
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], "Beautiful Villa")
        self.assertEqual(response.data['agent_name'], "Agent One")
        
        # Verify DB entry
        self.assertEqual(Listing.objects.filter(agent=self.agent_user).count(), 1)

    def test_create_listing_high_precision_coordinates(self):
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        data = {
            "title": "GPS Precision Penthouse",
            "category": "apartment",
            "price": "25000000.00",
            "address": "Victoria Island, Lagos",
            "latitude": "6.428123456789123",
            "longitude": "3.421987654321987",
            "bedrooms": 3,
            "bathrooms": 3
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(float(response.data['latitude']), 6.428123456789123)
        self.assertEqual(float(response.data['longitude']), 3.421987654321987)

    def test_create_listing_no_trailing_zeros_in_coordinates(self):
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        data = {
            "title": "Short Decimals Property",
            "category": "apartment",
            "price": "18000000.00",
            "address": "Benin City, Edo",
            "latitude": "6.38344",
            "longitude": "5.6113",
            "bedrooms": 2,
            "bathrooms": 2
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Assert clean numeric output without trailing zeroes
        self.assertEqual(response.data['latitude'], 6.38344)
        self.assertEqual(response.data['longitude'], 5.6113)
        self.assertNotEqual(str(response.data['latitude']), "6.383440000000000")
        self.assertNotEqual(str(response.data['longitude']), "5.611300000000000")

    def test_create_listing_with_image_urls(self):
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        data = {
            "title": "Luxury Mansion with URLs",
            "category": "villa",
            "price": "85000000.00",
            "address": "Banana Island, Lagos",
            "latitude": "6.465400",
            "longitude": "3.460100",
            "image_urls": [
                "https://box4realestate.cloud/media/listings/house1.webp",
                "https://box4realestate.cloud/media/listings/house2.webp"
            ]
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(response.data['cover_photo'])
        self.assertEqual(len(response.data['images']), 2)

    def test_create_listing_with_explicit_thumbnail_url(self):
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        data = {
            "title": "Villa with Thumbnail Selection",
            "category": "villa",
            "price": "90000000.00",
            "address": "Ikoyi, Lagos",
            "latitude": "6.454400",
            "longitude": "3.439200",
            "cover_photo_url": "https://box4realestate.cloud/media/listings/house2.webp",
            "image_urls": [
                "https://box4realestate.cloud/media/listings/house1.webp",
                "https://box4realestate.cloud/media/listings/house2.webp"
            ]
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('house2.webp', response.data['cover_photo'])

    def test_create_listing_denied_for_buyer(self):
        token = self.get_jwt_token("buyer1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        data = {
            "title": "Nice Condo",
            "category": "condo",
            "price": "5000000.00",
            "address": "Yaba, Lagos",
            "latitude": "6.524400",
            "longitude": "3.379200",
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_listing_creation_has_no_artificial_cap(self):
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Create multiple listings without max_listings cap
        for i in range(5):
            Listing.objects.create(
                agent=self.agent_user,
                title=f"Listing {i}",
                category=self.cat_house,
                price=5000000,
                address="Address",
                latitude=6.0,
                longitude=3.0
            )

        # Attempt to create another listing (should succeed since max_listings is removed)
        data = {
            "title": "Sixth Listing",
            "category": str(self.cat_house.id),
            "price": "5000000.00",
            "address": "Address",
            "latitude": "6.000000",
            "longitude": "3.000000"
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


    def test_partial_update_on_put_and_patch(self):
        # Create listing
        listing = Listing.objects.create(
            agent=self.agent_user,
            title="Old Title",
            category=self.cat_apartment,
            price=2000000,
            address="Address",
            latitude=6.0,
            longitude=3.0
        )
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        detail_url = reverse('listing-detail', kwargs={'pk': listing.id})

        # Test PATCH (partial)
        patch_response = self.client.patch(detail_url, {"title": "New Title"})
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_response.data['title'], "New Title")
        self.assertEqual(patch_response.data['category'], self.cat_apartment.id) # Unchanged

        # Test PUT (should also support partial updates in our viewset)
        put_response = self.client.put(detail_url, {"price": "2500000.00"})
        self.assertEqual(put_response.status_code, status.HTTP_200_OK)
        self.assertEqual(put_response.data['title'], "New Title") # Maintained
        self.assertEqual(float(put_response.data['price']), 2500000.00)

    def test_edit_denied_for_non_owner(self):
        listing = Listing.objects.create(
            agent=self.agent_user,
            title="Agent One's Listing",
            category=self.cat_house,
            price=3000000,
            address="Address",
            latitude=6.0,
            longitude=3.0
        )
        # Login other agent
        token = self.get_jwt_token("agent2@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        detail_url = reverse('listing-detail', kwargs={'pk': listing.id})
        response = self.client.patch(detail_url, {"title": "Hacked Title"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_boost_listing_limit(self):
        # Create two listings for agent1
        listing1 = Listing.objects.create(
            agent=self.agent_user, title="Listing 1", category=self.cat_house, price=5000000, address="Addr", latitude=6.0, longitude=3.0
        )
        listing2 = Listing.objects.create(
            agent=self.agent_user, title="Listing 2", category=self.cat_house, price=5000000, address="Addr", latitude=6.0, longitude=3.0
        )

        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        boost_url1 = reverse('listing-boost', kwargs={'pk': listing1.id})
        boost_url2 = reverse('listing-boost', kwargs={'pk': listing2.id})

        # Boost 1st listing (Silver limit is 1)
        response1 = self.client.post(boost_url1)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertTrue(response1.data['is_boosted'])

        # Attempt to boost 2nd listing (should fail due to 1 limit)
        response2 = self.client.post(boost_url2)
        self.assertEqual(response2.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("limit of 1", response2.data['error'])

        # Unboost 1st listing
        unboost_response = self.client.post(boost_url1, {"action": "unboost"})
        self.assertEqual(unboost_response.status_code, status.HTTP_200_OK)
        self.assertFalse(unboost_response.data['is_boosted'])

        # Boost 2nd listing (should succeed now)
        success_response = self.client.post(boost_url2)
        self.assertEqual(success_response.status_code, status.HTTP_200_OK)
        self.assertTrue(success_response.data['is_boosted'])

    def test_feature_listing_limit(self):
        # Create two listings
        listing1 = Listing.objects.create(
            agent=self.agent_user, title="Listing 1", category=self.cat_house, price=5000000, address="Addr", latitude=6.0, longitude=3.0
        )
        listing2 = Listing.objects.create(
            agent=self.agent_user, title="Listing 2", category=self.cat_house, price=5000000, address="Addr", latitude=6.0, longitude=3.0
        )

        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        feature_url1 = reverse('listing-feature', kwargs={'pk': listing1.id})
        feature_url2 = reverse('listing-feature', kwargs={'pk': listing2.id})

        # Feature 1st listing (Silver limit is 1)
        response1 = self.client.post(feature_url1)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertTrue(response1.data['is_featured'])

        # Attempt to feature 2nd listing (should fail)
        response2 = self.client.post(feature_url2)
        self.assertEqual(response2.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("reached your plan limit", response2.data['error'])

    def test_upload_and_delete_listing_photos(self):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 1. Step 2 Upload: Agent uploads 2 property photos before creating the listing record
        img_io1 = io.BytesIO()
        Image.new('RGB', (800, 600), color='red').save(img_io1, format='JPEG')
        img_file1 = SimpleUploadedFile("house1.jpg", img_io1.getvalue(), content_type="image/jpeg")

        img_io2 = io.BytesIO()
        Image.new('RGB', (800, 600), color='blue').save(img_io2, format='JPEG')
        img_file2 = SimpleUploadedFile("house2.jpg", img_io2.getvalue(), content_type="image/jpeg")

        upload_url = reverse('listing-upload-photos')
        upload_res = self.client.post(upload_url, {'images': [img_file1, img_file2]}, format='multipart')
        self.assertEqual(upload_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(upload_res.data['images']), 2)

        uploaded_img_ids = [img['id'] for img in upload_res.data['images']]

        # 2. Step 3: Agent creates the listing and links the pre-uploaded image IDs
        create_data = {
            "title": "Luxury Mansion",
            "category": str(self.cat_villa.id),
            "price": "25000000.00",
            "address": "Victoria Island, Lagos",
            "latitude": "6.428100",
            "longitude": "3.421900",
            "image_ids": uploaded_img_ids
        }
        create_res = self.client.post(self.list_url, create_data, format='json')
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(create_res.data['images']), 2)

        # 3. Test deleting a photo by image_id (matches the 'x' remove button on cards)
        delete_photo_id = uploaded_img_ids[1]
        delete_url = reverse('listing-delete-photo', kwargs={'image_id': delete_photo_id})
        delete_res = self.client.delete(delete_url)
        self.assertEqual(delete_res.status_code, status.HTTP_200_OK)

        # Verify photo count reduced to 1
        listing_obj = Listing.objects.get(pk=create_res.data['id'])
        self.assertEqual(listing_obj.images.count(), 1)

    def test_agent_dashboard_overview_and_my_listings_endpoints(self):
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 1. Create property for agent1
        Listing.objects.create(
            agent=self.agent_user,
            title="Luxury Apartment in Lekki",
            category=self.cat_apartment,
            price=10000000.00,
            address="Ikorodu street lagos",
            latitude=6.4,
            longitude=3.4,
            views_count=17,
            status="active"
        )

        # 2. Test Agent Dashboard Endpoint (Screen 1 UI)
        dash_url = reverse('agent-dashboard')
        dash_res = self.client.get(dash_url)
        self.assertEqual(dash_res.status_code, status.HTTP_200_OK)
        self.assertIn("Hey,", dash_res.data['greeting'])
        self.assertIn("active_listings", dash_res.data['metrics'])
        self.assertIn("subscription", dash_res.data['metrics'])
        self.assertEqual(len(dash_res.data['active_listings']), 1)

        # 3. Test Agent My Listings Endpoint (Screen 2 UI)
        my_listings_url = reverse('agent-my-listings')
        my_res = self.client.get(my_listings_url, {'type': 'all'})
        self.assertEqual(my_res.status_code, status.HTTP_200_OK)
        results = my_res.data['results'] if 'results' in my_res.data else my_res.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['views_count'], 17)

    def test_agent_profile_endpoint(self):
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        profile_url = reverse('agent-profile')
        get_res = self.client.get(profile_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)

        update_res = self.client.patch(profile_url, {"agency_name": "Lagos Realty", "bio": "Top property agent."})
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)
        self.assertEqual(update_res.data['agency_name'], "Lagos Realty")

    def test_unverified_agent_blocked_from_creating_listing(self):
        # Create unverified agent
        unverified_agent = User.objects.create_user(
            email="unverified@example.com",
            username="unverified@example.com",
            password="securepassword123",
            full_name="Unverified Agent",
            role="agent",
            is_email_verified=True
        )
        unverified_agent.agent_profile.plan = self.silver_plan
        unverified_agent.agent_profile.is_verified = False
        unverified_agent.agent_profile.save()
        
        from profiles.models import AgentKYC
        kyc, _ = AgentKYC.objects.get_or_create(agent_profile=unverified_agent.agent_profile)
        kyc.status = 'unverified'
        kyc.save()

        token = self.get_jwt_token("unverified@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        payload = {
            "title": "Blocked Listing",
            "category": "apartment",
            "price": "5000000.00",
            "address": "Victoria Island, Lagos",
            "latitude": 6.42,
            "longitude": 3.42,
            "bedrooms": 2,
            "bathrooms": 2,
        }
        res = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("KYC is not verified", str(res.data))

    def test_agent_kyc_verification_flow_and_status(self):
        # 1. Unverified agent submits valid NIN and CAC
        agent = User.objects.create_user(
            email="kycagent@example.com",
            username="kycagent@example.com",
            password="securepassword123",
            full_name="KYC Test Agent",
            role="agent",
            is_email_verified=True
        )
        agent.agent_profile.plan = self.silver_plan
        agent.agent_profile.save()

        token = self.get_jwt_token("kycagent@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Initial KYC status should be unverified
        status_url = reverse('agent-kyc-status')
        res = self.client.get(status_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'unverified')

        # Submit verification with invalid NIN length
        verify_url = reverse('agent-kyc-verify')
        bad_res = self.client.post(verify_url, {"nin_number": "12345"})
        self.assertEqual(bad_res.status_code, status.HTTP_400_BAD_REQUEST)

        # Submit verification with valid 11-digit NIN and CAC
        good_res = self.client.post(verify_url, {
            "nin_number": "12345678901",
            "cac_number": "RC1234567",
            "cac_company_type": "co",
            "agency_name": "Verified Properties Ltd"
        })
        self.assertEqual(good_res.status_code, status.HTTP_200_OK)
        self.assertEqual(good_res.data['kyc']['status'], 'verified')
        self.assertTrue(good_res.data['kyc']['nin_verified'])
        self.assertTrue(good_res.data['kyc']['cac_verified'])

        # Now check agent status endpoint returns verified
        status_res = self.client.get(status_url)
        self.assertEqual(status_res.status_code, status.HTTP_200_OK)
        self.assertEqual(status_res.data['status'], 'verified')

    def test_admin_agent_kyc_management(self):
        # Create admin user
        admin_user = User.objects.create_user(
            email="admin_kyc@example.com",
            username="admin_kyc@example.com",
            password="securepassword123",
            full_name="Admin User",
            role="admin",
            is_email_verified=True
        )
        admin_token = self.get_jwt_token("admin_kyc@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_token}')

        # 1. Admin lists all KYC records
        list_url = reverse('admin-kyc-agents-list')
        list_res = self.client.get(list_url)
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)

        # 2. Admin reviews and rejects an agent's KYC
        from profiles.models import AgentKYC
        kyc = AgentKYC.objects.first()
        review_url = reverse('admin-kyc-agent-review', kwargs={'pk': kyc.id})

        reject_res = self.client.post(review_url, {"action": "reject", "reason": "Name on NIN does not match photo"})
        self.assertEqual(reject_res.status_code, status.HTTP_200_OK)
        self.assertEqual(reject_res.data['kyc']['status'], 'failed')
        self.assertEqual(reject_res.data['kyc']['failure_reason'], "Name on NIN does not match photo")

        # 3. Admin reviews and approves the agent's KYC
        approve_res = self.client.post(review_url, {"action": "approve"})
        self.assertEqual(approve_res.status_code, status.HTTP_200_OK)
        self.assertEqual(approve_res.data['kyc']['status'], 'verified')

    def test_tag_list_and_listing_creation_with_tags_and_location(self):
        from agents.models import Tag
        tag1 = Tag.objects.create(name="Modern")
        tag2 = Tag.objects.create(name="Furnished")

        # 1. List tags
        tag_list_url = reverse('agent-tags')
        tag_res = self.client.get(tag_list_url)
        self.assertEqual(tag_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(tag_res.data), 2)

        # 2. Agent creates listing with tags, city, and state
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        payload = {
            "title": "Luxury Penthouse",
            "category": "Apartment",
            "price": "30000000.00",
            "address": "Victoria Island, Lagos",
            "city": "Victoria Island",
            "state": "Lagos",
            "country": "Nigeria",
            "latitude": "6.428100",
            "longitude": "3.421900",
            "bedrooms": 3,
            "bathrooms": 3,
            "tag": [str(tag1.id), str(tag2.id)],
            "facilities": ["Gym", "Elevator"]
        }
        res = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['city'], "Victoria Island")
        self.assertEqual(res.data['state'], "Lagos")
        self.assertEqual(len(res.data['tags']), 2)

    def test_agent_properties_search_and_filtering(self):
        from agents.models import Tag, Category
        tag_pool, _ = Tag.objects.get_or_create(name="Pool")
        tag_waterfront, _ = Tag.objects.get_or_create(name="Waterfront")
        cat_duplex, _ = Category.objects.get_or_create(name="Duplex")

        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        l1 = Listing.objects.create(
            agent=self.agent_user,
            title="Lekki Waterfront Villa",
            category=cat_duplex,
            price=50000000.00,
            address="Admiralty Way, Lekki",
            city="Lekki",
            state="Lagos",
            bedrooms=4,
            bathrooms=4,
            latitude=6.45,
            longitude=3.50,
            status="active"
        )
        l1.tag.add(tag_waterfront)

        l2 = Listing.objects.create(
            agent=self.agent_user,
            title="Abuja Smart Duplex",
            category=cat_duplex,
            price=30000000.00,
            address="Maitama, Abuja",
            city="Maitama",
            state="Abuja",
            bedrooms=3,
            bathrooms=3,
            latitude=9.08,
            longitude=7.49,
            status="active"
        )
        l2.tag.add(tag_pool)

        # 1. Search in ListingListCreateView by city
        res = self.client.get(self.list_url, {'search': 'Lekki'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data['results'] if 'results' in res.data else res.data
        self.assertTrue(any(r['title'] == "Lekki Waterfront Villa" for r in results))
        self.assertFalse(any(r['title'] == "Abuja Smart Duplex" for r in results))

        # 2. Filter in AgentMyListingsView by tag
        my_listings_url = reverse('agent-my-listings')
        res_tag = self.client.get(my_listings_url, {'tag': 'Waterfront'})
        self.assertEqual(res_tag.status_code, status.HTTP_200_OK)
        tag_results = res_tag.data['results'] if 'results' in res_tag.data else res_tag.data
        self.assertEqual(len(tag_results), 1)
        self.assertEqual(tag_results[0]['title'], "Lekki Waterfront Villa")

        # 3. Filter by state
        res_state = self.client.get(my_listings_url, {'state': 'Abuja'})
        self.assertEqual(res_state.status_code, status.HTTP_200_OK)
        state_results = res_state.data['results'] if 'results' in res_state.data else res_state.data
        self.assertEqual(len(state_results), 1)
        self.assertEqual(state_results[0]['title'], "Abuja Smart Duplex")

    def test_agent_subscription_flow_and_quota_status(self):
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 1. Create a Gold Plan
        gold_plan = Plan.objects.create(
            name="Gold Agency",
            price=49.99,
            billing_cycle="monthly",
            max_boosted=10,
            max_featured=5,
            max_images_per_listing=20,
            has_verified_badge=True
        )

        # 2. List available plans
        plans_res = self.client.get(reverse('agent-plans-list'))
        self.assertEqual(plans_res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(plans_res.data), 2)

        # 3. Subscribe to Gold Agency Plan
        sub_url = reverse('agent-subscription-subscribe')
        sub_res = self.client.post(sub_url, {
            "plan_id": str(gold_plan.id),
            "payment_method": "paystack",
            "transaction_reference": "TX-998877"
        })
        self.assertEqual(sub_res.status_code, status.HTTP_200_OK)
        self.assertEqual(sub_res.data['subscription']['plan_name'], "Gold Agency")

        # 4. Check Current Subscription Status
        status_url = reverse('agent-subscription-status')
        status_res = self.client.get(status_url)
        self.assertEqual(status_res.status_code, status.HTTP_200_OK)
        self.assertTrue(status_res.data['has_active_subscription'])
        self.assertEqual(status_res.data['plan']['name'], "Gold Agency")
        self.assertEqual(status_res.data['usage']['max_boosted'], 10)
        self.assertEqual(status_res.data['usage']['max_featured'], 5)
        self.assertEqual(status_res.data['usage']['max_images_per_listing'], 20)

        # 5. Check Subscription Billing History
        hist_url = reverse('agent-subscription-history')
        hist_res = self.client.get(hist_url)
        self.assertEqual(hist_res.status_code, status.HTTP_200_OK)
        history_results = hist_res.data['results'] if 'results' in hist_res.data else hist_res.data
        self.assertEqual(len(history_results), 1)
        self.assertEqual(history_results[0]['plan_name'], "Gold Agency")

        # 6. Cancel Subscription
        cancel_url = reverse('agent-subscription-cancel')
        cancel_res = self.client.post(cancel_url)
        self.assertEqual(cancel_res.status_code, status.HTTP_200_OK)
        self.agent_profile.refresh_from_db()
        self.assertIsNone(self.agent_profile.plan)

    def test_agent_pay_as_you_boost_custom_duration(self):
        from profiles.models import BoostPlan, ListingBoostPlacement
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 1. Admin creates a 14-day and a 30-day boost package
        boost_14 = BoostPlan.objects.create(name="14 Days Mega Boost", duration_days=14, price=4500.00)
        boost_30 = BoostPlan.objects.create(name="30 Days Ultra Boost", duration_days=30, price=8000.00)

        # 2. Agent fetches available boost packages
        boost_list_res = self.client.get(reverse('agent-boost-plans-list'))
        self.assertEqual(boost_list_res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(boost_list_res.data), 2)

        # 3. Agent creates a listing and boosts it with the 14-day package
        listing = Listing.objects.create(
            agent=self.agent_user, title="Boostable Property", category=self.cat_house, price=5000000, address="Addr", latitude=6.0, longitude=3.0
        )
        boost_url = reverse('listing-boost', kwargs={'pk': listing.id})
        boost_res = self.client.post(boost_url, {
            "boost_plan_id": str(boost_14.id),
            "payment_method": "card",
            "payment_reference": "REF-BOOST-14"
        })
        self.assertEqual(boost_res.status_code, status.HTTP_200_OK)
        self.assertTrue(boost_res.data['is_boosted'])
        self.assertEqual(boost_res.data['placement']['duration_days'], 14)
        self.assertEqual(boost_res.data['placement']['boost_plan_name'], "14 Days Mega Boost")

        # Verify DB placement
        placement = ListingBoostPlacement.objects.filter(listing=listing, status='active').first()
        self.assertIsNotNone(placement)
        self.assertEqual(placement.duration_days, 14)
        self.assertEqual(placement.payment_reference, "REF-BOOST-14")

    def test_agent_listing_views_numbers_and_summary(self):
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        from buyers.models import ListingView

        # Create two listings for agent
        listing1 = Listing.objects.create(
            agent=self.agent_user, title="View Tracked Listing 1", category=self.cat_house, price=10000000, address="Addr 1", latitude=6.0, longitude=3.0
        )
        listing2 = Listing.objects.create(
            agent=self.agent_user, title="View Tracked Listing 2", category=self.cat_house, price=15000000, address="Addr 2", latitude=6.0, longitude=3.0
        )

        # Buyer views listing 1
        ListingView.objects.create(buyer=self.buyer_user, listing=listing1)
        listing1.views_count = 1
        listing1.save()

        # 1. Test single listing views numbers endpoint
        detail_view_url = reverse('agent-listing-views-tracker', kwargs={'pk': listing1.id})
        res = self.client.get(detail_view_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['listing_id'], str(listing1.id))
        self.assertEqual(res.data['title'], "View Tracked Listing 1")
        self.assertEqual(res.data['total_views'], 1)
        self.assertEqual(res.data['views_today'], 1)
        self.assertEqual(res.data['views_this_week'], 1)
        self.assertEqual(res.data['views_this_month'], 1)
        # Ensure no buyer personal info is exposed in response
        self.assertNotIn('buyers', res.data)
        self.assertNotIn('viewers', res.data)

        # 2. Test overall agent views summary endpoint
        summary_url = reverse('agent-listings-views-summary')
        sum_res = self.client.get(summary_url)
        self.assertEqual(sum_res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(sum_res.data['total_properties'], 2)
        self.assertGreaterEqual(sum_res.data['total_views'], 1)
        self.assertEqual(sum_res.data['views_today'], 1)
        self.assertGreaterEqual(len(sum_res.data['properties']), 2)
        # Verify property items in summary contain view counts only
        for prop in sum_res.data['properties']:
            self.assertIn('views_count', prop)
            self.assertNotIn('buyers', prop)




