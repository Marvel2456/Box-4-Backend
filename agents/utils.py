from django.utils import timezone
from profiles.models import BoostPlan, ListingBoostPlacement
from agents.models import Listing


def get_default_boost_plan():
    """
    Retrieves the first active BoostPlan configured by admin,
    or creates a default active BoostPlan if none exists.
    """
    plan = BoostPlan.objects.filter(is_active=True).order_by('duration_days', 'price').first()
    if not plan:
        plan, _ = BoostPlan.objects.get_or_create(
            name="Standard Boost",
            duration_days=7,
            defaults={
                "price": 2500.00,
                "description": "7-day listing boost configured by admin on the dashboard.",
                "features": [
                    "Top placement on buyer search results",
                    "Priority ranking in property feed",
                    "Highlighted boost badge"
                ],
                "is_active": True
            }
        )
    return plan


def expire_outdated_boosts():
    """
    Checks and expires any active ListingBoostPlacement records where date_expires has passed.
    Reverts listing.is_boosted to False if the listing has no other active boost placements.
    Returns the count of placements expired in this run.
    """
    from django.db import transaction as db_transaction

    now = timezone.now()
    with db_transaction.atomic():
        expired_placements = ListingBoostPlacement.objects.select_for_update().filter(
            status='active',
            date_expires__lte=now
        )
        listing_ids = list(expired_placements.values_list('listing_id', flat=True).distinct())
        if not listing_ids:
            return 0

        count = expired_placements.update(status='expired', updated_at=now)

        for listing_id in listing_ids:
            has_active = ListingBoostPlacement.objects.filter(
                listing_id=listing_id,
                status='active',
                date_expires__gt=now
            ).exists()
            if not has_active:
                Listing.objects.select_for_update().filter(id=listing_id).update(is_boosted=False, updated_at=now)

    return count
