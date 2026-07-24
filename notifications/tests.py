from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from agents.models import Listing
from profiles.models import Plan
from .models import Notification

User = get_user_model()

class NotificationAPITests(APITestCase):
    def setUp(self):
        self.plan = Plan.objects.create(name="Gold", price=19.99, max_listings=10)

        self.agent_user = User.objects.create_user(
            email="notifagent@example.com",
            username="notifagent@example.com",
            password="securepassword123",
            full_name="Notif Agent",
            role="agent"
        )
        self.agent_user.agent_profile.plan = self.plan
        self.agent_user.agent_profile.save()

        self.buyer_user = User.objects.create_user(
            email="notifbuyer@example.com",
            username="notifbuyer@example.com",
            password="securepassword123",
            full_name="Notif Buyer",
            role="buyer"
        )
        self.buyer_user.is_email_verified = True
        self.buyer_user.save()

        self.listing = Listing.objects.create(
            agent=self.agent_user,
            title="Notification Villa",
            category="house",
            price=15000000.00,
            address="Lagos",
            latitude=6.524400,
            longitude=3.379200
        )

        # Create notifications for agent
        self.notif1 = Notification.objects.create(
            recipient=self.agent_user,
            sender=self.buyer_user,
            notification_type="saved_listing",
            title="Listing Saved",
            message="Buyer saved your listing",
            listing=self.listing,
            is_read=False
        )
        self.notif2 = Notification.objects.create(
            recipient=self.agent_user,
            sender=self.buyer_user,
            notification_type="message",
            title="New Message",
            message="Buyer sent a message",
            is_read=False
        )

        self.list_url = reverse('notifications-list')
        self.unread_count_url = reverse('notifications-unread-count')
        self.read_all_url = reverse('notifications-read-all')

    def get_jwt_token(self, email, password):
        response = self.client.post(reverse('auth_login'), {"email": email, "password": password})
        return response.data['access']

    def test_notification_list_and_pagination(self):
        token = self.get_jwt_token("notifagent@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify paginated response structure
        self.assertIn("count", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(response.data["count"], 2)

    def test_unread_count_and_mark_as_read(self):
        token = self.get_jwt_token("notifagent@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Unread count
        count_res = self.client.get(self.unread_count_url)
        self.assertEqual(count_res.status_code, status.HTTP_200_OK)
        self.assertEqual(count_res.data["unread_count"], 2)

        # Mark single as read
        read_detail_url = reverse('notifications-mark-as-read', kwargs={'pk': self.notif1.id})
        mark_res = self.client.patch(read_detail_url)
        self.assertEqual(mark_res.status_code, status.HTTP_200_OK)
        self.assertTrue(mark_res.data["is_read"])

        # Mark all as read
        read_all_res = self.client.post(self.read_all_url)
        self.assertEqual(read_all_res.status_code, status.HTTP_200_OK)

        # Verify unread count is 0
        count_res2 = self.client.get(self.unread_count_url)
        self.assertEqual(count_res2.data["unread_count"], 0)

    def test_automatic_notification_trigger_on_save(self):
        token = self.get_jwt_token("notifbuyer@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        saved_url = reverse('buyer-saved-list')
        save_res = self.client.post(saved_url, {"listing_id": str(self.listing.id)})
        self.assertEqual(save_res.status_code, status.HTTP_201_CREATED)

        # Verify notification was created for agent
        agent_notifs = Notification.objects.filter(recipient=self.agent_user, notification_type="saved_listing")
        self.assertTrue(agent_notifs.exists())
