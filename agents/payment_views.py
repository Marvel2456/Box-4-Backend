import uuid
import logging
from datetime import timedelta
from django.db import transaction as db_transaction, IntegrityError
from django.contrib.auth import get_user_model
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
User = get_user_model()


def extract_scoped_idempotency_key(request, explicit_key=None):
    """
    Extracts an idempotency key from the request headers ('Idempotency-Key' or 'X-Idempotency-Key')
    or request payload ('idempotency_key'), scoped to the authenticated user ID.
    """
    raw_key = (
        explicit_key
        or request.headers.get('Idempotency-Key')
        or request.headers.get('X-Idempotency-Key')
        or request.META.get('HTTP_IDEMPOTENCY_KEY')
        or request.META.get('HTTP_X_IDEMPOTENCY_KEY')
    )
    if not raw_key and isinstance(getattr(request, 'data', None), dict):
        raw_key = request.data.get('idempotency_key')

    if not raw_key or not str(raw_key).strip():
        return None

    clean_key = str(raw_key).strip()[:90]
    user_id = getattr(getattr(request, 'user', None), 'id', 'anon')
    return f"{user_id}:{clean_key}"


def _build_verification_response_payload(transaction, idempotent_replay=False):
    result_payload = {
        "message": "Payment verified and activated successfully!",
        "status": "success",
        "reference": transaction.reference,
        "transaction_type": transaction.transaction_type,
        "amount": float(transaction.amount),
        "paid_at": transaction.paid_at,
        "idempotent_replay": idempotent_replay,
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

    return result_payload


def fulfill_payment_transaction(transaction, paystack_data=None):
    """
    Atomically and idempotently fulfills an approved Paystack transaction:
    - Acquires a row-level lock (select_for_update) on PaymentTransaction
    - Prevents race conditions between concurrent webhook and client verification calls
    - Activates agent subscription or listing boost exactly once per reference
    - Updates PaymentTransaction status to 'success'
    """
    with db_transaction.atomic():
        locked_tx = (
            PaymentTransaction.objects
            .select_for_update()
            .select_related('user', 'plan', 'boost_plan', 'listing')
            .get(pk=transaction.pk)
        )

        if locked_tx.status == 'success':
            if paystack_data and not locked_tx.paystack_response:
                locked_tx.paystack_response = paystack_data
                locked_tx.payment_channel = paystack_data.get('channel') or locked_tx.payment_channel
                locked_tx.save(update_fields=['paystack_response', 'payment_channel', 'updated_at'])
            return locked_tx

        now = timezone.now()
        locked_tx.status = 'success'
        locked_tx.paid_at = locked_tx.paid_at or now
        if paystack_data:
            locked_tx.paystack_response = paystack_data
            locked_tx.payment_channel = paystack_data.get('channel') or locked_tx.payment_channel
        locked_tx.save()

        user = locked_tx.user

        # 1. Fulfill Subscription atomically
        if locked_tx.transaction_type == 'subscription' and locked_tx.plan:
            plan = locked_tx.plan
            days_duration = 30
            if plan.billing_cycle == 'quarterly':
                days_duration = 90
            elif plan.billing_cycle == 'yearly':
                days_duration = 365

            renewal_date = now + timedelta(days=days_duration)

            # Lock user row and profile to serialize concurrent subscription updates for this agent
            User.objects.select_for_update().filter(pk=user.pk).first()
            profile, _ = AgentProfile.objects.select_for_create_or_lock(user=user) if hasattr(AgentProfile.objects, 'select_for_create_or_lock') else AgentProfile.objects.get_or_create(user=user)
            profile = AgentProfile.objects.select_for_update().get(pk=profile.pk)

            # Check if subscription for this transaction reference already exists (idempotency guard)
            existing_sub = (
                AgentSubscription.objects
                .select_for_update()
                .filter(agent=user, transaction_reference=locked_tx.reference)
                .first()
            )
            if existing_sub:
                AgentSubscription.objects.filter(agent=user, status='active').exclude(pk=existing_sub.pk).update(status='cancelled')
                if existing_sub.status != 'active':
                    existing_sub.status = 'active'
                    existing_sub.save(update_fields=['status', 'updated_at'])
            else:
                # Deactivate previous active subscriptions under lock
                AgentSubscription.objects.select_for_update().filter(agent=user, status='active').update(status='cancelled')

                # Create active subscription record
                AgentSubscription.objects.create(
                    agent=user,
                    plan=plan,
                    amount=locked_tx.amount,
                    next_renewal=renewal_date,
                    status='active',
                    auto_renew=True,
                    payment_method='paystack',
                    transaction_reference=locked_tx.reference
                )

            profile.plan = plan
            if plan.has_verified_badge:
                profile.is_verified = True
            profile.save()

        # 2. Fulfill Listing Boost atomically
        elif locked_tx.transaction_type == 'boost' and locked_tx.listing:
            listing = Listing.objects.select_for_update().get(pk=locked_tx.listing.pk)
            boost_plan = locked_tx.boost_plan
            duration_days = boost_plan.duration_days if boost_plan else 7
            date_expires = now + timedelta(days=duration_days)

            # Idempotency check: ensure placement for this reference hasn't already been created
            existing_placement = (
                ListingBoostPlacement.objects
                .select_for_update()
                .filter(listing=listing, payment_reference=locked_tx.reference)
                .first()
            )
            if existing_placement:
                ListingBoostPlacement.objects.filter(listing=listing, status='active').exclude(pk=existing_placement.pk).update(status='expired')
                if existing_placement.status != 'active':
                    existing_placement.status = 'active'
                    existing_placement.save(update_fields=['status', 'updated_at'])
            else:
                # Expire older active placements under lock
                ListingBoostPlacement.objects.select_for_update().filter(listing=listing, status='active').update(status='expired')

                ListingBoostPlacement.objects.create(
                    listing=listing,
                    agent=user,
                    boost_plan=boost_plan,
                    amount=locked_tx.amount,
                    duration_days=duration_days,
                    date_expires=date_expires,
                    status='active',
                    payment_reference=locked_tx.reference
                )

            listing.is_boosted = True
            listing.save(update_fields=['is_boosted', 'updated_at'])
            locked_tx.listing = listing

        return locked_tx


class PaymentInitializeView(generics.GenericAPIView):
    """
    Initialize a Paystack checkout for either an Agent Subscription Plan or Listing Boost.
    Supports idempotency via 'Idempotency-Key' header or 'idempotency_key' field,
    plus automatic deduplication of concurrent double-clicks.
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

        if payment_type == 'boost' and listing.agent != user and user.role != 'admin':
            return Response(
                {"error": "You do not have permission to boost this listing."},
                status=status.HTTP_403_FORBIDDEN
            )

        scoped_idempotency_key = extract_scoped_idempotency_key(
            request,
            explicit_key=serializer.validated_data.get('idempotency_key')
        )

        if payment_type == 'subscription':
            amount = plan.price
            item_name = f"Subscription: {plan.name} ({plan.billing_cycle})"
        else:
            amount = boost_plan.price if boost_plan else 2500.00
            item_name = f"Boost: {listing.title} ({boost_plan.duration_days if boost_plan else 7} days)"

        with db_transaction.atomic():
            # Lock the user row to serialize concurrent initialization requests from the same user
            User.objects.select_for_update().filter(pk=user.pk).first()

            existing_tx = None
            if scoped_idempotency_key:
                existing_tx = (
                    PaymentTransaction.objects
                    .select_for_update()
                    .filter(idempotency_key=scoped_idempotency_key)
                    .first()
                )
            else:
                # Automatic double-click protection: reuse an identical pending transaction created within the last 30 seconds
                recent_cutoff = timezone.now() - timedelta(seconds=30)
                existing_tx = (
                    PaymentTransaction.objects
                    .select_for_update()
                    .filter(
                        user=user,
                        transaction_type=payment_type,
                        plan=plan,
                        boost_plan=boost_plan,
                        listing=listing,
                        amount=amount,
                        status='pending',
                        created_at__gte=recent_cutoff,
                    )
                    .order_by('-created_at')
                    .first()
                )

            if existing_tx:
                if existing_tx.status == 'success':
                    return Response({
                        "message": "Payment already completed for this request.",
                        "status": "success",
                        "reference": existing_tx.reference,
                        "amount": float(existing_tx.amount),
                        "currency": existing_tx.currency,
                        "public_key": settings.PAYSTACK_PUBLIC_KEY,
                        "idempotent_replay": True
                    }, status=status.HTTP_200_OK)

                cached_data = (existing_tx.paystack_response or {}).get('data') or {}
                if existing_tx.status == 'pending' and cached_data.get('authorization_url'):
                    return Response({
                        "message": "Payment initialized successfully.",
                        "authorization_url": cached_data.get('authorization_url'),
                        "access_code": cached_data.get('access_code'),
                        "reference": existing_tx.reference,
                        "amount": float(existing_tx.amount),
                        "currency": existing_tx.currency,
                        "public_key": settings.PAYSTACK_PUBLIC_KEY,
                        "idempotent_replay": True
                    }, status=status.HTTP_200_OK)

            unique_suffix = uuid.uuid4().hex[:10]
            if payment_type == 'subscription':
                reference = f"SUB_{user.id}_{unique_suffix}"
            else:
                reference = f"BOOST_{listing.id}_{unique_suffix}"

            if existing_tx and existing_tx.status in ['pending', 'failed']:
                # Reuse the row if it had a failed/incomplete initialization with the same idempotency_key
                existing_tx.reference = reference
                existing_tx.amount = amount
                existing_tx.status = 'pending'
                existing_tx.plan = plan
                existing_tx.boost_plan = boost_plan
                existing_tx.listing = listing
                existing_tx.save()
                transaction = existing_tx
            else:
                transaction = PaymentTransaction.objects.create(
                    user=user,
                    reference=reference,
                    idempotency_key=scoped_idempotency_key,
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

        # Call Paystack initialize API outside the DB lock
        paystack_res = paystack_service.initialize_payment(
            email=user.email,
            amount=amount,
            reference=reference,
            callback_url=callback_url,
            metadata=metadata
        )

        if not paystack_res.get('status'):
            PaymentTransaction.objects.filter(pk=transaction.pk).update(
                status='failed',
                paystack_response=paystack_res,
                updated_at=timezone.now()
            )
            return Response({
                "error": paystack_res.get('message', "Unable to initialize Paystack payment.")
            }, status=status.HTTP_400_BAD_REQUEST)

        PaymentTransaction.objects.filter(pk=transaction.pk).update(
            paystack_response=paystack_res,
            updated_at=timezone.now()
        )

        paystack_data = paystack_res.get('data', {})
        return Response({
            "message": "Payment initialized successfully.",
            "authorization_url": paystack_data.get('authorization_url'),
            "access_code": paystack_data.get('access_code'),
            "reference": reference,
            "amount": float(amount),
            "currency": "NGN",
            "public_key": settings.PAYSTACK_PUBLIC_KEY,
            "idempotent_replay": False
        }, status=status.HTTP_200_OK)


class PaymentVerifyView(generics.GenericAPIView):
    """
    Verify a Paystack transaction by reference and activate the subscription or listing boost.
    Idempotent and concurrency-safe against simultaneous webhook or duplicate verify requests.
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

        reference = serializer.validated_data['reference'].strip()

        # Find existing transaction
        transaction = (
            PaymentTransaction.objects
            .select_related('user', 'plan', 'boost_plan', 'listing')
            .filter(reference=reference)
            .first()
        )

        if transaction and transaction.user != request.user and request.user.role != 'admin':
            return Response(
                {"error": "You do not have permission to verify this payment reference."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Fast-path idempotency: if already fulfilled (e.g. by webhook or earlier verify call), return immediately
        if transaction and transaction.status == 'success':
            return Response(
                _build_verification_response_payload(transaction, idempotent_replay=True),
                status=status.HTTP_200_OK
            )

        # Call Paystack verify API
        paystack_res = paystack_service.verify_payment(reference)

        if not paystack_res.get('status'):
            if transaction:
                with db_transaction.atomic():
                    locked_tx = PaymentTransaction.objects.select_for_update().get(pk=transaction.pk)
                    if locked_tx.status != 'success':
                        locked_tx.status = 'failed'
                        locked_tx.paystack_response = paystack_res
                        locked_tx.save(update_fields=['status', 'paystack_response', 'updated_at'])
            return Response({
                "error": paystack_res.get('message', "Transaction verification failed.")
            }, status=status.HTTP_400_BAD_REQUEST)

        data = paystack_res.get('data', {})
        gateway_status = data.get('status')

        if gateway_status != 'success':
            if transaction:
                with db_transaction.atomic():
                    locked_tx = PaymentTransaction.objects.select_for_update().get(pk=transaction.pk)
                    if locked_tx.status != 'success':
                        locked_tx.status = 'failed' if gateway_status in ['failed', 'reversed'] else 'abandoned'
                        locked_tx.paystack_response = data
                        locked_tx.save(update_fields=['status', 'paystack_response', 'updated_at'])
            return Response({
                "error": f"Payment was not successful. Gateway status: {gateway_status}",
                "gateway_response": data.get('gateway_response')
            }, status=status.HTTP_400_BAD_REQUEST)

        # Reconstruct transaction safely if created externally or via mobile SDK direct popup
        if not transaction:
            metadata = data.get('metadata') or {}
            payment_type = metadata.get('payment_type', 'subscription')
            plan_id = metadata.get('plan_id')
            listing_id = metadata.get('listing_id')
            boost_plan_id = metadata.get('boost_plan_id')

            plan = Plan.objects.filter(id=plan_id).first() if plan_id else None
            listing = Listing.objects.filter(id=listing_id).first() if listing_id else None
            boost_plan = BoostPlan.objects.filter(id=boost_plan_id).first() if boost_plan_id else None

            amount_kobo = data.get('amount', 0)
            amount = amount_kobo / 100.0 if amount_kobo else 0.0

            try:
                with db_transaction.atomic():
                    transaction, _ = PaymentTransaction.objects.get_or_create(
                        reference=reference,
                        defaults={
                            'user': request.user,
                            'transaction_type': payment_type,
                            'amount': amount,
                            'currency': data.get('currency', 'NGN'),
                            'status': 'pending',
                            'plan': plan,
                            'boost_plan': boost_plan,
                            'listing': listing,
                        }
                    )
            except IntegrityError:
                transaction = PaymentTransaction.objects.get(reference=reference)

        was_already_success = (transaction.status == 'success')
        transaction = fulfill_payment_transaction(transaction, data)

        return Response(
            _build_verification_response_payload(transaction, idempotent_replay=was_already_success),
            status=status.HTTP_200_OK
        )


class PaystackWebhookView(APIView):
    """
    Paystack Webhook receiver for automated asynchronous charge verification.
    Concurrency-safe and idempotent.
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
            reference = (data.get('reference') or '').strip()
            if reference:
                transaction = PaymentTransaction.objects.filter(reference=reference).first()
                if not transaction:
                    # Reconstruct from metadata if webhook arrived for an externally-initialized transaction
                    metadata = data.get('metadata') or {}
                    user_id = metadata.get('user_id')
                    user = User.objects.filter(id=user_id).first() if user_id else None
                    if user:
                        payment_type = metadata.get('payment_type', 'subscription')
                        plan_id = metadata.get('plan_id')
                        listing_id = metadata.get('listing_id')
                        boost_plan_id = metadata.get('boost_plan_id')

                        plan = Plan.objects.filter(id=plan_id).first() if plan_id else None
                        listing = Listing.objects.filter(id=listing_id).first() if listing_id else None
                        boost_plan = BoostPlan.objects.filter(id=boost_plan_id).first() if boost_plan_id else None
                        amount_kobo = data.get('amount', 0)
                        amount = amount_kobo / 100.0 if amount_kobo else 0.0

                        try:
                            with db_transaction.atomic():
                                transaction, _ = PaymentTransaction.objects.get_or_create(
                                    reference=reference,
                                    defaults={
                                        'user': user,
                                        'transaction_type': payment_type,
                                        'amount': amount,
                                        'currency': data.get('currency', 'NGN'),
                                        'status': 'pending',
                                        'plan': plan,
                                        'boost_plan': boost_plan,
                                        'listing': listing,
                                    }
                                )
                        except IntegrityError:
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
