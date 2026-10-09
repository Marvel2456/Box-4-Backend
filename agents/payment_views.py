import uuid
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from profiles.models import (
    Plan, BoostPlan, AgentProfile, AgentSubscription,
    ListingBoostPlacement, PaymentTransaction
)
from agents.models import Listing
from core.paystack import paystack_service
from .payment_serializers import (
    PaymentInitializeRequestSerializer,
    PaymentInitializeResponseSerializer,
    PaymentVerifyRequestSerializer,
    PaymentTransactionSerializer,
)

logger = logging.getLogger(__name__)


def fulfill_payment_transaction(transaction, paystack_data=None):
    """
    Idempotently fulfills an approved Paystack transaction:
    - Activates agent subscription or listing boost
    - Updates PaymentTransaction status to 'success'
    """
    if transaction.status == 'success':
        return transaction

    transaction.status = 'success'
    transaction.paid_at = timezone.now()
    if paystack_data:
        transaction.paystack_response = paystack_data
        transaction.payment_channel = paystack_data.get('channel') or transaction.payment_channel
    transaction.save()

    user = transaction.user

    # 1. Fulfill Subscription
    if transaction.transaction_type == 'subscription' and transaction.plan:
        plan = transaction.plan
        days_duration = 30
        if plan.billing_cycle == 'quarterly':
            days_duration = 90
        elif plan.billing_cycle == 'yearly':
            days_duration = 365

        renewal_date = timezone.now() + timedelta(days=days_duration)

        # Deactivate previous active subscriptions
        AgentSubscription.objects.filter(agent=user, status='active').update(status='cancelled')

        # Create active subscription record
        AgentSubscription.objects.create(
            agent=user,
            plan=plan,
            amount=transaction.amount,
            next_renewal=renewal_date,
            status='active',
            auto_renew=True,
            payment_method='paystack',
            transaction_reference=transaction.reference
        )

        # Update profile
        profile, _ = AgentProfile.objects.get_or_create(user=user)
        profile.plan = plan
        if plan.has_verified_badge:
            profile.is_verified = True
        profile.save()

    # 2. Fulfill Listing Boost
    elif transaction.transaction_type == 'boost' and transaction.listing:
        listing = transaction.listing
        boost_plan = transaction.boost_plan
        duration_days = boost_plan.duration_days if boost_plan else 7
        date_expires = timezone.now() + timedelta(days=duration_days)

        # Expire older active placements
        ListingBoostPlacement.objects.filter(listing=listing, status='active').update(status='expired')

        ListingBoostPlacement.objects.create(
            listing=listing,
            agent=user,
            boost_plan=boost_plan,
            amount=transaction.amount,
            duration_days=duration_days,
            date_expires=date_expires,
            status='active',
            payment_reference=transaction.reference
        )

        listing.is_boosted = True
        listing.save()

    return transaction


class PaymentInitializeView(generics.GenericAPIView):
    """
    Initialize a Paystack checkout for either an Agent Subscription Plan or Listing Boost.
    Returns authorization URL, access code, transaction reference, and public key.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentInitializeRequestSerializer

    @swagger_auto_schema(
        operation_description="Initialize a Paystack payment session for Subscription or Property Boost.",
        request_body=PaymentInitializeRequestSerializer,
        responses={200: PaymentInitializeResponseSerializer}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        payment_type = serializer.validated_data['payment_type']
        callback_url = serializer.validated_data.get('callback_url')

        plan = serializer.validated_data.get('plan_obj')
        listing = serializer.validated_data.get('listing_obj')
        boost_plan = serializer.validated_data.get('boost_plan_obj')

        # Determine price and reference
        unique_suffix = uuid.uuid4().hex[:10]
        if payment_type == 'subscription':
            amount = plan.price
            reference = f"SUB_{user.id}_{unique_suffix}"
            item_name = f"Subscription: {plan.name} ({plan.billing_cycle})"
        else:
            if listing.agent != user and user.role != 'admin':
                return Response(
                    {"error": "You do not have permission to boost this listing."},
                    status=status.HTTP_403_FORBIDDEN
                )
            amount = boost_plan.price if boost_plan else 2500.00
            reference = f"BOOST_{listing.id}_{unique_suffix}"
            item_name = f"Boost: {listing.title} ({boost_plan.duration_days if boost_plan else 7} days)"

        # Save initial pending transaction in database
        transaction = PaymentTransaction.objects.create(
            user=user,
            reference=reference,
            transaction_type=payment_type,
            amount=amount,
            currency='NGN',
            status='pending',
            plan=plan,
            boost_plan=boost_plan,
            listing=listing
        )

        metadata = {
            'user_id': str(user.id),
            'user_email': user.email,
            'payment_type': payment_type,
            'plan_id': str(plan.id) if plan else None,
            'listing_id': str(listing.id) if listing else None,
            'boost_plan_id': str(boost_plan.id) if boost_plan else None,
            'item_name': item_name,
            'transaction_id': str(transaction.id)
        }

        # Call Paystack initialize API
        paystack_res = paystack_service.initialize_payment(
            email=user.email,
            amount=amount,
            reference=reference,
            callback_url=callback_url,
            metadata=metadata
        )

        if not paystack_res.get('status'):
            transaction.status = 'failed'
            transaction.paystack_response = paystack_res
            transaction.save()
            return Response({
                "error": paystack_res.get('message', "Unable to initialize Paystack payment.")
            }, status=status.HTTP_400_BAD_REQUEST)

        paystack_data = paystack_res.get('data', {})
        return Response({
            "message": "Payment initialized successfully.",
            "authorization_url": paystack_data.get('authorization_url'),
            "access_code": paystack_data.get('access_code'),
            "reference": reference,
            "amount": float(amount),
            "currency": "NGN",
            "public_key": settings.PAYSTACK_PUBLIC_KEY
        }, status=status.HTTP_200_OK)


class PaymentVerifyView(generics.GenericAPIView):
    """
    Verify a Paystack transaction by reference and activate the subscription or listing boost.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentVerifyRequestSerializer

    @swagger_auto_schema(
        operation_description="Verify Paystack payment reference and fulfill subscription or listing boost.",
        request_body=PaymentVerifyRequestSerializer,
        responses={200: openapi.Response(description="Payment verified and service activated.")}
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reference = serializer.validated_data['reference']

        # Find existing transaction
        transaction = PaymentTransaction.objects.filter(reference=reference).first()

        # Call Paystack verify API
        paystack_res = paystack_service.verify_payment(reference)

        if not paystack_res.get('status'):
            if transaction:
                transaction.status = 'failed'
                transaction.paystack_response = paystack_res
                transaction.save()
            return Response({
                "error": paystack_res.get('message', "Transaction verification failed.")
            }, status=status.HTTP_400_BAD_REQUEST)

        data = paystack_res.get('data', {})
        gateway_status = data.get('status')

        if gateway_status != 'success':
            if transaction:
                transaction.status = 'failed' if gateway_status in ['failed', 'reversed'] else 'abandoned'
                transaction.paystack_response = data
                transaction.save()
            return Response({
                "error": f"Payment was not successful. Gateway status: {gateway_status}",
                "gateway_response": data.get('gateway_response')
            }, status=status.HTTP_400_BAD_REQUEST)

        # Reconstruct transaction if created externally or via mobile SDK direct popup
        if not transaction:
            metadata = data.get('metadata') or {}
            payment_type = metadata.get('payment_type', 'subscription')
            plan_id = metadata.get('plan_id')
            listing_id = metadata.get('listing_id')
            boost_plan_id = metadata.get('boost_plan_id')

            plan = Plan.objects.filter(id=plan_id).first() if plan_id else None
            listing = Listing.objects.filter(id=listing_id).first() if listing_id else None
            boost_plan = BoostPlan.objects.filter(id=boost_plan_id).first() if boost_plan_id else None

            # Amount in Naira
            amount_kobo = data.get('amount', 0)
            amount = amount_kobo / 100.0 if amount_kobo else 0.0

            transaction = PaymentTransaction.objects.create(
                user=request.user,
                reference=reference,
                transaction_type=payment_type,
                amount=amount,
                currency=data.get('currency', 'NGN'),
                status='pending',
                plan=plan,
                boost_plan=boost_plan,
                listing=listing
            )

        # Fulfill transaction
        transaction = fulfill_payment_transaction(transaction, data)

        result_payload = {
            "message": "Payment verified and activated successfully!",
            "status": "success",
            "reference": reference,
            "transaction_type": transaction.transaction_type,
            "amount": float(transaction.amount),
            "paid_at": transaction.paid_at
        }

        if transaction.transaction_type == 'subscription' and transaction.plan:
            result_payload["subscription"] = {
                "plan_name": transaction.plan.name,
                "billing_cycle": transaction.plan.billing_cycle,
                "price": float(transaction.plan.price)
            }
        elif transaction.transaction_type == 'boost' and transaction.listing:
            result_payload["boost"] = {
                "listing_id": str(transaction.listing.id),
                "listing_title": transaction.listing.title,
                "is_boosted": transaction.listing.is_boosted,
                "duration_days": transaction.boost_plan.duration_days if transaction.boost_plan else 7
            }

        return Response(result_payload, status=status.HTTP_200_OK)


class PaystackWebhookView(APIView):
    """
    Paystack Webhook receiver for automated asynchronous charge verification.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        signature = request.headers.get('x-paystack-signature') or request.META.get('HTTP_X_PAYSTACK_SIGNATURE')

        if settings.PAYSTACK_SECRET_KEY:
            is_valid = paystack_service.verify_webhook_signature(request.body, signature)
            if not is_valid:
                logger.warning("Rejected Paystack webhook: Invalid signature")
                return Response({"error": "Invalid webhook signature"}, status=status.HTTP_400_BAD_REQUEST)

        event_data = request.data
        event_name = event_data.get('event')

        if event_name == 'charge.success':
            data = event_data.get('data', {})
            reference = data.get('reference')
            if reference:
                transaction = PaymentTransaction.objects.filter(reference=reference).first()
                if transaction:
                    fulfill_payment_transaction(transaction, data)
                    logger.info(f"Paystack webhook fulfilled transaction: {reference}")

        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class PaymentTransactionHistoryView(generics.ListAPIView):
    """
    Get audit history of all payment transactions for the authenticated user.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentTransactionSerializer

    def get_queryset(self):
        return PaymentTransaction.objects.filter(user=self.request.user).order_by('-created_at')

    @swagger_auto_schema(
        operation_description="Get list of past payment transactions for the authenticated user.",
        responses={200: PaymentTransactionSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
