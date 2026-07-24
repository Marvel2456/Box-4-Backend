from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from django.utils import timezone
from agents.models import Listing, Report
from profiles.models import Plan, AgentProfile, AgentSubscription, FeaturedPlan, ListingFeature

User = get_user_model()

class AdminPortalAPITests(APITestCase):
    def setUp(self):
        # 1. Superadmin/Admin user
        self.admin_user = User.objects.create_user(
            email="superadmin@example.com",
            username="superadmin@example.com",
            password="adminpassword123",
            full_name="Super Admin",
            role="admin",
            is_staff=True,
            is_superuser=True
        )

        # 2. Buyer and Agent users
        self.buyer_user = User.objects.create_user(
            email="buyer@example.com",
            username="buyer@example.com",
            password="buyerpassword123",
            full_name="Regular Buyer",
            role="buyer"
        )
        self.agent_user = User.objects.create_user(
            email="agent@example.com",
            username="agent@example.com",
            password="agentpassword123",
            full_name="Real Estate Agent",
            role="agent"
        )

        # Create listings
        self.plan = Plan.objects.create(name="Gold", price=49.99, max_listings=10)
        self.agent_user.agent_profile.plan = self.plan
        self.agent_user.agent_profile.save()

        Listing.objects.create(
            agent=self.agent_user,
            title="Active Duplex",
            category="duplex",
            price=50000000.00,
            address="Lekki, Lagos",
            latitude=6.428100,
            longitude=3.421900,
            status="active",
            is_published=True
        )
        Listing.objects.create(
            agent=self.agent_user,
            title="Pending Villa",
            category="villa",
            price=150000000.00,
            address="Maitama, Abuja",
            latitude=9.076500,
            longitude=7.398600,
            status="pending",
            is_published=False
        )

        # Endpoint URLs
        self.register_url = reverse('admin-auth-register')
        self.login_url = reverse('admin-auth-login')
        self.invite_url = reverse('admin-invite')
        self.change_pass_url = reverse('admin-auth-change-password')
        self.overview_url = reverse('admin-overview')

    def get_admin_jwt_token(self):
        response = self.client.post(self.login_url, {
            "email": "superadmin@example.com",
            "password": "adminpassword123"
        })
        return response.data['access']

    def test_admin_registration_and_login(self):
        # Register new admin
        reg_data = {
            "email": "newadmin@example.com",
            "password": "newadminpassword123",
            "full_name": "New Admin"
        }
        reg_res = self.client.post(self.register_url, reg_data)
        self.assertEqual(reg_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(reg_res.data['user']['role'], 'admin')

        # Login new admin
        login_res = self.client.post(self.login_url, {
            "email": "newadmin@example.com",
            "password": "newadminpassword123"
        })
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_res.data)
        self.assertFalse(login_res.data['must_change_password'])

    def test_login_rejected_for_non_admin(self):
        # Buyer login attempt
        buyer_res = self.client.post(self.login_url, {
            "email": "buyer@example.com",
            "password": "buyerpassword123"
        })
        self.assertEqual(buyer_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Access denied", str(buyer_res.data))

        # Agent login attempt
        agent_res = self.client.post(self.login_url, {
            "email": "agent@example.com",
            "password": "agentpassword123"
        })
        self.assertEqual(agent_res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Access denied", str(agent_res.data))

    @patch('admin_portal.views.send_mail')
    def test_admin_invite_and_password_change_flow(self, mock_send_mail):
        token = self.get_admin_jwt_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Invite new admin
        invite_data = {
            "email": "invitedadmin@example.com",
            "full_name": "Invited Admin",
            "phone_number": "08012345678"
        }
        invite_res = self.client.post(self.invite_url, invite_data)
        self.assertEqual(invite_res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(invite_res.data['invited_user']['must_change_password'])
        mock_send_mail.assert_called_once()

        # Check invited user in DB
        invited_user = User.objects.get(email="invitedadmin@example.com")
        self.assertEqual(invited_user.role, 'admin')
        self.assertTrue(invited_user.must_change_password)

        # Login as invited admin with temporary password sent in email call args
        email_message_text = mock_send_mail.call_args[0][1]
        temp_pass = email_message_text.split("Temporary Password: ")[1].split("\n")[0]

        login_res = self.client.post(self.login_url, {
            "email": "invitedadmin@example.com",
            "password": temp_pass
        })
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertTrue(login_res.data['must_change_password'])

        # Change password
        invited_token = login_res.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {invited_token}')
        change_res = self.client.post(self.change_pass_url, {
            "old_password": temp_pass,
            "new_password": "NewPermanentPassword123!"
        })
        self.assertEqual(change_res.status_code, status.HTTP_200_OK)

        # Verify must_change_password is cleared
        invited_user.refresh_from_db()
        self.assertFalse(invited_user.must_change_password)

    def test_overview_dashboard_analytics(self):
        token = self.get_admin_jwt_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = self.client.get(self.overview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("overview", response.data)
        self.assertIn("listings_added_last_30_days", response.data)
        self.assertIn("listings_by_type", response.data)
        self.assertIn("recent_listings", response.data)
        self.assertIn("pending_approvals", response.data)

        # Check overview stat card keys
        overview = response.data['overview']
        self.assertEqual(overview['total_properties']['count'], 2)
        self.assertEqual(overview['agents']['count'], 1)
        self.assertEqual(overview['pending_approvals']['count'], 1)

    def test_all_properties_list_and_filtering(self):
        token = self.get_admin_jwt_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        all_url = reverse('admin-properties-all')
        response = self.client.get(all_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

        # Filter by category
        cat_res = self.client.get(f"{all_url}?category=duplex")
        self.assertEqual(cat_res.status_code, status.HTTP_200_OK)
        self.assertEqual(cat_res.data['count'], 1)

    def test_pending_properties_approval_and_rejection(self):
        token = self.get_admin_jwt_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        pending_url = reverse('admin-properties-pending')
        response = self.client.get(pending_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('header_stats', response.data)
        self.assertEqual(response.data['header_stats']['awaiting_review']['count'], 1)

        # Approve property
        pending_listing = Listing.objects.get(title="Pending Villa")
        approve_url = reverse('admin-properties-approve', kwargs={'pk': pending_listing.id})
        app_res = self.client.post(approve_url)
        self.assertEqual(app_res.status_code, status.HTTP_200_OK)
        
        pending_listing.refresh_from_db()
        self.assertEqual(pending_listing.status, 'active')
        self.assertTrue(pending_listing.is_published)

        # Reject property
        reject_url = reverse('admin-properties-reject', kwargs={'pk': pending_listing.id})
        rej_res = self.client.post(reject_url)
        self.assertEqual(rej_res.status_code, status.HTTP_200_OK)
        
        pending_listing.refresh_from_db()
        self.assertEqual(pending_listing.status, 'rejected')

    def test_featured_and_sold_properties(self):
        token = self.get_admin_jwt_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        active_listing = Listing.objects.get(title="Active Duplex")
        
        # Feature property
        feature_url = reverse('admin-properties-toggle-feature', kwargs={'pk': active_listing.id})
        feat_res = self.client.post(feature_url)
        self.assertEqual(feat_res.status_code, status.HTTP_200_OK)
        self.assertTrue(feat_res.data['is_featured'])

        # Check featured list
        featured_list_url = reverse('admin-properties-featured')
        featured_res = self.client.get(featured_list_url)
        self.assertEqual(featured_res.status_code, status.HTTP_200_OK)
        self.assertEqual(featured_res.data['header_stats']['currently_featured']['count'], 1)

        # Mark property as sold
        sold_url = reverse('admin-properties-mark-sold', kwargs={'pk': active_listing.id})
        sold_res = self.client.post(sold_url)
        self.assertEqual(sold_res.status_code, status.HTTP_200_OK)
        
        # Check sold list
        sold_list_url = reverse('admin-properties-sold')
        sold_list_res = self.client.get(sold_list_url)
        self.assertEqual(sold_list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(sold_list_res.data['header_stats']['sold_count'], 1)

    def test_agents_list_and_verification_actions(self):
        token = self.get_admin_jwt_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Check Agents List
        agents_url = reverse('admin-users-agents')
        res = self.client.get(agents_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('header_stats', res.data)
        self.assertEqual(res.data['header_stats']['total_agents'], 1)

        # Check Verification Queue
        queue_url = reverse('admin-users-verification-queue')
        queue_res = self.client.get(queue_url)
        self.assertEqual(queue_res.status_code, status.HTTP_200_OK)

        # Approve verification
        approve_url = reverse('admin-users-approve-verification', kwargs={'pk': self.agent_user.id})
        app_res = self.client.post(approve_url)
        self.assertEqual(app_res.status_code, status.HTTP_200_OK)

        self.agent_user.agent_profile.refresh_from_db()
        self.assertTrue(self.agent_user.agent_profile.is_verified)

    def test_buyers_list_and_suspend_actions(self):
        token = self.get_admin_jwt_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # Create buyer user
        buyer = User.objects.create_user(
            email="buyer1@example.com",
            username="buyer1@example.com",
            password="Password123!",
            role="buyer",
            full_name="Jane Buyer"
        )

        # Check Buyers List
        buyers_url = reverse('admin-users-buyers')
        res = self.client.get(buyers_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('header_stats', res.data)
        self.assertEqual(res.data['header_stats']['total_users']['count'], 2)

        # Suspend buyer
        suspend_url = reverse('admin-users-suspend', kwargs={'pk': buyer.id})
        sus_res = self.client.post(suspend_url)
        self.assertEqual(sus_res.status_code, status.HTTP_200_OK)

        buyer.refresh_from_db()
        self.assertTrue(buyer.is_suspended)

        # Check Suspended list
        suspended_url = reverse('admin-users-suspended')
        susp_list_res = self.client.get(f"{suspended_url}?role=buyer")
        self.assertEqual(susp_list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(susp_list_res.data['header_stats']['suspended_buyers'], 1)

        # Unsuspend buyer
        unsuspend_url = reverse('admin-users-unsuspend', kwargs={'pk': buyer.id})
        unsus_res = self.client.post(unsuspend_url)
        self.assertEqual(unsus_res.status_code, status.HTTP_200_OK)

        buyer.refresh_from_db()
        self.assertFalse(buyer.is_suspended)

    def test_reports_moderation_list_and_actions(self):
        token = self.get_admin_jwt_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        active_listing = Listing.objects.get(title="Active Duplex")
        report = Report.objects.create(
            report_type='listing',
            reason='Fake images',
            listing=active_listing,
            reporter=self.buyer_user
        )

        # Check Reports list
        reports_url = reverse('admin-reports-list')
        res = self.client.get(reports_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('header_stats', res.data)
        self.assertEqual(res.data['header_stats']['reported_listings'], 1)

        # Check Moderation list alias
        mod_url = reverse('admin-moderation-list')
        mod_res = self.client.get(mod_url)
        self.assertEqual(mod_res.status_code, status.HTTP_200_OK)

        # Resolve report
        resolve_url = reverse('admin-report-resolve', kwargs={'pk': report.id})
        res_res = self.client.post(resolve_url)
        self.assertEqual(res_res.status_code, status.HTTP_200_OK)

        report.refresh_from_db()
        self.assertEqual(report.status, 'resolved')

        # Dismiss report
        dismiss_url = reverse('admin-report-dismiss', kwargs={'pk': report.id})
        dis_res = self.client.post(dismiss_url)
        self.assertEqual(dis_res.status_code, status.HTTP_200_OK)

        report.refresh_from_db()
        self.assertEqual(report.status, 'dismissed')

    def test_finance_endpoints_and_detail_views(self):
        token = self.get_admin_jwt_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        # 1. Create test AgentSubscription and ListingFeature
        test_plan = Plan.objects.create(name="Gold Plan Test", price=49.99)
        sub = AgentSubscription.objects.create(
            agent=self.agent_user,
            plan=test_plan,
            amount=8500.00,
            next_renewal=timezone.now() + timezone.timedelta(days=30),
            status='active'
        )

        featured_plan = FeaturedPlan.objects.create(
            name="14 day plan",
            duration_days=14,
            price=8500.00,
            features=["Homepage hero slot", "Priority search rank"]
        )

        active_listing = Listing.objects.get(title="Active Duplex")
        feature = ListingFeature.objects.create(
            listing=active_listing,
            featured_plan=featured_plan,
            amount=8500.00,
            date_due=timezone.now() + timezone.timedelta(days=14),
            status='active'
        )

        # 2. Check Subscriptions List
        subs_url = reverse('admin-finance-subscriptions')
        subs_res = self.client.get(subs_url)
        self.assertEqual(subs_res.status_code, status.HTTP_200_OK)
        self.assertIn('header_stats', subs_res.data)
        self.assertIn('plans', subs_res.data)

        # 3. Check Subscription Details View
        sub_detail_url = reverse('admin-finance-subscription-detail', kwargs={'pk': sub.id})
        sub_det_res = self.client.get(sub_detail_url)
        self.assertEqual(sub_det_res.status_code, status.HTTP_200_OK)
        self.assertEqual(sub_det_res.data['agent_email'], self.agent_user.email)

        # 4. Check Send Subscription Reminder Action
        sub_rem_url = reverse('admin-finance-subscription-send-reminder', kwargs={'pk': sub.id})
        sub_rem_res = self.client.post(sub_rem_url)
        self.assertEqual(sub_rem_res.status_code, status.HTTP_200_OK)

        # 5. Check Revenue Overview View
        rev_url = reverse('admin-finance-revenue-overview')
        rev_res = self.client.get(rev_url)
        self.assertEqual(rev_res.status_code, status.HTTP_200_OK)
        self.assertIn('chart_data', rev_res.data)

        # 6. Check Features List View
        feat_list_url = reverse('admin-finance-features')
        feat_list_res = self.client.get(feat_list_url)
        self.assertEqual(feat_list_res.status_code, status.HTTP_200_OK)

        # 7. Check Feature Details View
        feat_detail_url = reverse('admin-finance-feature-detail', kwargs={'pk': feature.id})
        feat_det_res = self.client.get(feat_detail_url)
        self.assertEqual(feat_det_res.status_code, status.HTTP_200_OK)
        self.assertEqual(feat_det_res.data['listing']['id'], str(active_listing.id))

        # 8. Check Send Feature Reminder Action
        feat_rem_url = reverse('admin-finance-feature-send-reminder', kwargs={'pk': feature.id})
        feat_rem_res = self.client.post(feat_rem_url)
        self.assertEqual(feat_rem_res.status_code, status.HTTP_200_OK)

    def test_moderator_role_permissions(self):
        # 1. Admin invites a moderator user
        admin_token = self.get_admin_jwt_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_token}')

        invite_url = reverse('admin-invite')
        invite_res = self.client.post(invite_url, {
            "email": "mod1@example.com",
            "full_name": "Mod User One",
            "phone_number": "+234800000000",
            "role": "moderator"
        })
        self.assertEqual(invite_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(invite_res.data['invited_user']['role'], 'moderator')

        mod_user = User.objects.get(email="mod1@example.com")
        self.assertEqual(mod_user.role, 'moderator')

        # 2. Login as Moderator
        login_url = reverse('admin-auth-login')
        login_res = self.client.post(login_url, {
            "email": "mod1@example.com",
            "password": "TempPass1000!" # fallback or reset
        })
        # Generate token directly for mod_user
        from rest_framework_simplejwt.tokens import RefreshToken
        mod_token = str(RefreshToken.for_user(mod_user).access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {mod_token}')

        # 3. Moderator CAN access Overview, Properties, Users, Moderation
        self.assertEqual(self.client.get(reverse('admin-overview')).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse('admin-properties-all')).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse('admin-users-agents')).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse('admin-reports-list')).status_code, status.HTTP_200_OK)

        # 4. Moderator CANNOT access Finance revenue, subscriptions, features listing
        self.assertEqual(self.client.get(reverse('admin-finance-revenue-overview')).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(reverse('admin-finance-subscriptions')).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.get(reverse('admin-finance-features')).status_code, status.HTTP_403_FORBIDDEN)

        # 5. Moderator CANNOT invite other users
        self.assertEqual(self.client.post(invite_url, {
            "email": "mod2@example.com",
            "full_name": "Mod User Two",
            "phone_number": "+234800000001",
            "role": "moderator"
        }).status_code, status.HTTP_403_FORBIDDEN)





