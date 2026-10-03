from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import override_settings
from unittest.mock import patch

from agents.models import Listing, Category
from profiles.models import Plan
from .models import ChatRoom, Message

User = get_user_model()

class ChatAPITests(APITestCase):
    def setUp(self):
        self.plan = Plan.objects.create(name="Gold", price=19.99, max_boosted=5)
        
        self.agent_user = User.objects.create_user(
            email="chatagent@example.com",
            username="chatagent@example.com",
            password="securepassword123",
            full_name="Chat Agent",
            role="agent"
        )
        self.agent_user.agent_profile.plan = self.plan
        self.agent_user.agent_profile.save()

        self.buyer_user = User.objects.create_user(
            email="chatbuyer@example.com",
            username="chatbuyer@example.com",
            password="securepassword123",
            full_name="Chat Buyer",
            role="buyer"
        )
        self.buyer_user.is_email_verified = True
        self.buyer_user.save()

        self.cat_house, _ = Category.objects.get_or_create(name="House")

        self.listing = Listing.objects.create(
            agent=self.agent_user,
            title="Chat Property",
            category=self.cat_house,
            price=10000000.00,
            address="Lagos",
            latitude=6.524400,
            longitude=3.379200
        )

        self.send_url = reverse('chat-messages-send')
        self.conversations_url = reverse('chat-messages-conversations')
        self.contact_agent_url = reverse('contact-agent')
        self.mark_read_url = reverse('chat-messages-mark-read')
        self.unread_count_url = reverse('chat-messages-unread-count')

    def get_jwt_token(self, email, password):
        response = self.client.post(reverse('auth_login'), {"email": email, "password": password})
        return response.data['access']

    @override_settings(PUSHER_APP_ID='123456', PUSHER_KEY='test_key', PUSHER_SECRET='test_secret')
    @patch('core.firebase.send_push_notification')
    @patch('pusher.Pusher.trigger')
    def test_messaging_and_contact_agent_flow(self, mock_trigger, mock_fcm):
        token = self.get_jwt_token("chatbuyer@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 1. Contact Agent for listing
        contact_data = {
            "listing_id": str(self.listing.id),
            "message": "Hi, I want to inspect this property."
        }
        contact_res = self.client.post(self.contact_agent_url, contact_data)
        self.assertEqual(contact_res.status_code, status.HTTP_201_CREATED)
        self.assertIn("initiated", contact_res.data['message'])
        self.assertIn("chatroom_id", contact_res.data)
        self.assertIn("channel_name", contact_res.data)
        self.assertEqual(contact_res.data['event'], "new_message")

        # Verify chatroom created
        chatroom_id = contact_res.data['chatroom_id']
        room = ChatRoom.objects.get(id=chatroom_id)
        self.assertEqual(room.messages.count(), 1)
        self.assertTrue(room.participants.filter(id=self.buyer_user.id).exists())
        self.assertTrue(room.participants.filter(id=self.agent_user.id).exists())

        # 2. Send direct message in the room
        msg_data = {
            "receiver_id": str(self.agent_user.id),
            "message": "When are you free for a viewing?"
        }
        send_res = self.client.post(self.send_url, msg_data)
        self.assertEqual(send_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(send_res.data['channel_name'], room.channel_name)
        self.assertEqual(send_res.data['event'], "new_message")
        self.assertFalse(send_res.data['is_read'])

        # 3. Verify Agent Unread Count
        agent_token = self.get_jwt_token("chatagent@example.com", "securepassword123")
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {agent_token}')

        unread_res = self.client.get(self.unread_count_url)
        self.assertEqual(unread_res.status_code, status.HTTP_200_OK)
        self.assertEqual(unread_res.data['unread_count'], 2)

        # 4. Get active conversations as Agent
        conv_res = self.client.get(self.conversations_url)
        self.assertEqual(conv_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(conv_res.data), 1)
        self.assertEqual(conv_res.data[0]['chat_partner']['email'], "chatbuyer@example.com")
        self.assertEqual(conv_res.data[0]['last_message'], "When are you free for a viewing?")
        self.assertEqual(conv_res.data[0]['unread_count'], 2)
        self.assertEqual(conv_res.data[0]['channel_name'], room.channel_name)
        self.assertEqual(conv_res.data[0]['event'], "new_message")

        # 5. Mark messages as read
        read_res = self.client.post(self.mark_read_url, {"chatroom_id": str(room.id)})
        self.assertEqual(read_res.status_code, status.HTTP_200_OK)
        self.assertEqual(read_res.data['marked_count'], 2)
        self.assertEqual(read_res.data['unread_count'], 0)

        # 6. Verify messages in DB are marked read
        for msg in room.messages.all():
            self.assertTrue(msg.is_read)
            self.assertIsNotNone(msg.read_at)

        # 7. Get chat history
        history_url = reverse('chat-messages-history', kwargs={'identifier': self.buyer_user.id})
        hist_res = self.client.get(history_url)
        self.assertEqual(hist_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(hist_res.data), 2)
        self.assertTrue(hist_res.data[0]['is_read'])
