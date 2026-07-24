from django.urls import path
from .views import (
    AdminRegisterView,
    AdminLoginView,
    AdminInviteView,
    AdminChangePasswordView,
    OverviewDashboardView,
    AdminAllPropertiesListView,
    AdminPendingPropertiesListView,
    AdminApprovePropertyView,
    AdminRejectPropertyView,
    AdminBulkApprovePropertiesView,
    AdminFeaturedPropertiesListView,
    AdminToggleFeaturePropertyView,
    AdminSoldPropertiesListView,
    AdminMarkSoldPropertyView,
    AdminAgentsListView,
    AdminBuyersListView,
    AdminVerificationQueueListView,
    AdminApproveAgentVerificationView,
    AdminRejectAgentVerificationView,
    AdminSuspendedUsersListView,
    AdminSuspendUserView,
    AdminUnsuspendUserView,
    AdminReportsModerationListView,
    AdminResolveReportView,
    AdminDismissReportView,
    AdminSubscriptionsListView,
    AdminPlanCreateView,
    AdminPlanDetailView,
    AdminRevenueOverviewView,
    AdminFeaturedPlansListView,
    AdminFeaturedPlanCreateView,
    AdminFeaturedPlanDetailView,
    AdminSubscriptionDetailView,
    AdminSendSubscriptionReminderView,
    AdminFeatureDetailView,
    AdminSendFeatureReminderView
)

urlpatterns = [
    # Admin Auth
    path('auth/register/', AdminRegisterView.as_view(), name='admin-auth-register'),
    path('auth/login/', AdminLoginView.as_view(), name='admin-auth-login'),
    path('auth/change-password/', AdminChangePasswordView.as_view(), name='admin-auth-change-password'),

    # Admin Management
    path('admins/invite/', AdminInviteView.as_view(), name='admin-invite'),

    # Analytics Overview Dashboard
    path('overview/', OverviewDashboardView.as_view(), name='admin-overview'),

    # Property Listings Management
    path('properties/', AdminAllPropertiesListView.as_view(), name='admin-properties-all'),
    path('properties/pending/', AdminPendingPropertiesListView.as_view(), name='admin-properties-pending'),
    path('properties/<uuid:pk>/approve/', AdminApprovePropertyView.as_view(), name='admin-properties-approve'),
    path('properties/<uuid:pk>/reject/', AdminRejectPropertyView.as_view(), name='admin-properties-reject'),
    path('properties/bulk-approve/', AdminBulkApprovePropertiesView.as_view(), name='admin-properties-bulk-approve'),
    path('properties/featured/', AdminFeaturedPropertiesListView.as_view(), name='admin-properties-featured'),
    path('properties/<uuid:pk>/feature/', AdminToggleFeaturePropertyView.as_view(), name='admin-properties-toggle-feature'),
    path('properties/sold/', AdminSoldPropertiesListView.as_view(), name='admin-properties-sold'),
    path('properties/<uuid:pk>/mark-sold/', AdminMarkSoldPropertyView.as_view(), name='admin-properties-mark-sold'),

    # User Listings Management
    path('users/agents/', AdminAgentsListView.as_view(), name='admin-users-agents'),
    path('users/buyers/', AdminBuyersListView.as_view(), name='admin-users-buyers'),
    path('users/verification-queue/', AdminVerificationQueueListView.as_view(), name='admin-users-verification-queue'),
    path('users/<uuid:pk>/approve-verification/', AdminApproveAgentVerificationView.as_view(), name='admin-users-approve-verification'),
    path('users/<uuid:pk>/reject-verification/', AdminRejectAgentVerificationView.as_view(), name='admin-users-reject-verification'),
    path('users/suspended/', AdminSuspendedUsersListView.as_view(), name='admin-users-suspended'),
    path('users/<uuid:pk>/suspend/', AdminSuspendUserView.as_view(), name='admin-users-suspend'),
    path('users/<uuid:pk>/unsuspend/', AdminUnsuspendUserView.as_view(), name='admin-users-unsuspend'),

    # Reports & Moderation
    path('reports/', AdminReportsModerationListView.as_view(), name='admin-reports-list'),
    path('moderation/', AdminReportsModerationListView.as_view(), name='admin-moderation-list'),
    path('reports/<uuid:pk>/resolve/', AdminResolveReportView.as_view(), name='admin-report-resolve'),
    path('reports/<uuid:pk>/dismiss/', AdminDismissReportView.as_view(), name='admin-report-dismiss'),

    # Finance: Subscriptions & Revenue Overview
    path('finance/subscriptions/', AdminSubscriptionsListView.as_view(), name='admin-finance-subscriptions'),
    path('finance/subscriptions/<uuid:pk>/', AdminSubscriptionDetailView.as_view(), name='admin-finance-subscription-detail'),
    path('finance/subscriptions/<uuid:pk>/send-reminder/', AdminSendSubscriptionReminderView.as_view(), name='admin-finance-subscription-send-reminder'),
    path('finance/plans/', AdminPlanCreateView.as_view(), name='admin-finance-plans-create'),
    path('finance/plans/<uuid:pk>/', AdminPlanDetailView.as_view(), name='admin-finance-plans-detail'),
    path('finance/revenue-overview/', AdminRevenueOverviewView.as_view(), name='admin-finance-revenue-overview'),

    # Finance: Features & Featured Details
    path('finance/features/', AdminFeaturedPlansListView.as_view(), name='admin-finance-features'),
    path('finance/features/<uuid:pk>/', AdminFeatureDetailView.as_view(), name='admin-finance-feature-detail'),
    path('finance/features/<uuid:pk>/send-reminder/', AdminSendFeatureReminderView.as_view(), name='admin-finance-feature-send-reminder'),
    path('finance/featured-plans/', AdminFeaturedPlanCreateView.as_view(), name='admin-finance-featured-plans-create'),
    path('finance/featured-plans/<uuid:pk>/', AdminFeaturedPlanDetailView.as_view(), name='admin-finance-featured-plans-detail'),
]
