from rest_framework import serializers
from profiles.models import Plan, BoostPlan, PaymentTransaction
from agents.models import Listing


class PaymentInitializeRequestSerializer(serializers.Serializer):
    PAYMENT_TYPE_CHOICES = (
        ('subscription', 'Agent Subscription Plan'),
        ('boost', 'Listing Boost Package'),
    )

    payment_type = serializers.ChoiceField(
        choices=PAYMENT_TYPE_CHOICES,
        help_text="Type of payment: 'subscription' (for agent tier subscription) or 'boost' (for pay-as-you-boost listing)."
    )
    plan_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Required when payment_type is 'subscription'. UUID of the subscription plan to subscribe to."
    )
    listing_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Required when payment_type is 'boost'. UUID of the property listing to boost."
    )
    boost_plan_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional when payment_type is 'boost'. UUID of the boost package duration."
    )
    callback_url = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="Optional callback URL / deep-link to redirect the user after Paystack checkout."
    )

    def validate(self, attrs):
        payment_type = attrs.get('payment_type')
        if payment_type == 'subscription':
            plan_id = attrs.get('plan_id')
            if not plan_id:
                raise serializers.ValidationError({"plan_id": "plan_id is required when payment_type is 'subscription'."})
            try:
                plan = Plan.objects.get(pk=plan_id, is_active=True)
                attrs['plan_obj'] = plan
            except Plan.DoesNotExist:
                raise serializers.ValidationError({"plan_id": "Selected subscription plan does not exist or is inactive."})

        elif payment_type == 'boost':
            listing_id = attrs.get('listing_id')
            if not listing_id:
                raise serializers.ValidationError({"listing_id": "listing_id is required when payment_type is 'boost'."})
            try:
                listing = Listing.objects.get(pk=listing_id)
                attrs['listing_obj'] = listing
            except Listing.DoesNotExist:
                raise serializers.ValidationError({"listing_id": "Selected listing does not exist."})

            boost_plan_id = attrs.get('boost_plan_id')
            if boost_plan_id:
                try:
                    boost_plan = BoostPlan.objects.get(pk=boost_plan_id, is_active=True)
                    attrs['boost_plan_obj'] = boost_plan
                except BoostPlan.DoesNotExist:
                    raise serializers.ValidationError({"boost_plan_id": "Selected boost plan does not exist or is inactive."})
            else:
                from agents.utils import get_default_boost_plan
                attrs['boost_plan_obj'] = get_default_boost_plan()

        return attrs


class PaymentInitializeResponseSerializer(serializers.Serializer):
    authorization_url = serializers.CharField(help_text="Paystack checkout URL to redirect the user or open in WebView.")
    access_code = serializers.CharField(help_text="Paystack access code for mobile SDK checkout.")
    reference = serializers.CharField(help_text="Unique transaction reference.")
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, help_text="Amount in Naira.")
    currency = serializers.CharField(default='NGN')
    public_key = serializers.CharField(help_text="Paystack public key to plug into client SDK.")


class PaymentVerifyRequestSerializer(serializers.Serializer):
    reference = serializers.CharField(
        required=True,
        help_text="Paystack transaction reference to verify."
    )


class PaymentTransactionSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    plan_name = serializers.CharField(source='plan.name', default=None, read_only=True)
    boost_plan_name = serializers.CharField(source='boost_plan.name', default=None, read_only=True)
    listing_title = serializers.CharField(source='listing.title', default=None, read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'reference', 'transaction_type', 'amount', 'currency',
            'status', 'payment_channel', 'user_email', 'plan_name',
            'boost_plan_name', 'listing_title', 'paid_at', 'created_at'
        ]
        read_only_fields = fields
