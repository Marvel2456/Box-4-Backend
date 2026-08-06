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
            max_listings=3,
            max_boosted=1,
            max_featured=1
        )
        
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
        
        # Subscribe agent to plan
        self.agent_profile = self.agent_user.agent_profile
        self.agent_profile.plan = self.silver_plan
        self.agent_profile.save()

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
        self.other_agent.agent_profile.save()

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

    def test_listing_limit_enforced(self):
        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Create maximum listings (limit is 3)
        for i in range(3):
            Listing.objects.create(
                agent=self.agent_user,
                title=f"Listing {i}",
                category="house",
                price=5000000,
                address="Address",
                latitude=6.0,
                longitude=3.0
            )

        # Attempt to create the 4th listing (should be rejected)
        data = {
            "title": "Over Limit Listing",
            "category": "house",
            "price": "5000000.00",
            "address": "Address",
            "latitude": "6.000000",
            "longitude": "3.000000"
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("reached the maximum listing limit", response.data['non_field_errors'][0])

    def test_partial_update_on_put_and_patch(self):
        # Create listing
        listing = Listing.objects.create(
            agent=self.agent_user,
            title="Old Title",
            category="apartment",
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
        self.assertEqual(patch_response.data['category'], "apartment") # Unchanged

        # Test PUT (should also support partial updates in our viewset)
        put_response = self.client.put(detail_url, {"price": "2500000.00"})
        self.assertEqual(put_response.status_code, status.HTTP_200_OK)
        self.assertEqual(put_response.data['title'], "New Title") # Maintained
        self.assertEqual(float(put_response.data['price']), 2500000.00)

    def test_edit_denied_for_non_owner(self):
        listing = Listing.objects.create(
            agent=self.agent_user,
            title="Agent One's Listing",
            category="house",
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
            agent=self.agent_user, title="Listing 1", category="house", price=5000000, address="Addr", latitude=6.0, longitude=3.0
        )
        listing2 = Listing.objects.create(
            agent=self.agent_user, title="Listing 2", category="house", price=5000000, address="Addr", latitude=6.0, longitude=3.0
        )

        token = self.get_jwt_token("agent1@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        boost_url1 = reverse('listing-boost', kwargs={'pk': listing1.id})
        boost_url2 = reverse('listing-boost', kwargs={'pk': listing2.id})

        # Boost 1st listing (Silver limit is 1)
        response1 = self.client.post(boost_url1)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertTrue(response1.data['is_boosted'])

        # Attempt to boost 2nd listing (should fail)
        response2 = self.client.post(boost_url2)
        self.assertEqual(response2.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("reached your plan limit", response2.data['error'])

        # Unboost 1st listing
        unboost_response = self.client.post(boost_url1)
        self.assertEqual(unboost_response.status_code, status.HTTP_200_OK)
        self.assertFalse(unboost_response.data['is_boosted'])

        # Boost 2nd listing (should succeed now)
        success_response = self.client.post(boost_url2)
        self.assertEqual(success_response.status_code, status.HTTP_200_OK)
        self.assertTrue(success_response.data['is_boosted'])

    def test_feature_listing_limit(self):
        # Create two listings
        listing1 = Listing.objects.create(
            agent=self.agent_user, title="Listing 1", category="house", price=5000000, address="Addr", latitude=6.0, longitude=3.0
        )
        listing2 = Listing.objects.create(
            agent=self.agent_user, title="Listing 2", category="house", price=5000000, address="Addr", latitude=6.0, longitude=3.0
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
            "category": "villa",
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
            category="apartment",
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


