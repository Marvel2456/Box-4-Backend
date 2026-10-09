from django.urls import path
from .payment_views import (
    PaymentInitializeView,
    PaymentVerifyView,
    PaystackWebhookView,
    PaymentTransactionHistoryView,
)

urlpatterns = [
    path('initialize/', PaymentInitializeView.as_view(), name='payment-initialize'),
    path('verify/', PaymentVerifyView.as_view(), name='payment-verify'),
    path('webhook/', PaystackWebhookView.as_view(), name='paystack-webhook'),
    path('history/', PaymentTransactionHistoryView.as_view(), name='payment-history'),
]
