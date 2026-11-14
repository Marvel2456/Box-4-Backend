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
        expired_rows = list(
            ListingBoostPlacement.objects
            .select_for_update(skip_locked=True)
            .filter(status='active', date_expires__lte=now)
            .values_list('id', 'listing_id')
        )
        if not expired_rows:
            return 0

        placement_ids = [row[0] for row in expired_rows]
        listing_ids = list(dict.fromkeys(row[1] for row in expired_rows))

        count = ListingBoostPlacement.objects.filter(id__in=placement_ids).update(status='expired', updated_at=now)

        for listing_id in listing_ids:
            has_active = ListingBoostPlacement.objects.filter(
                listing_id=listing_id,
                status='active',
                date_expires__gt=now
            ).exists()
            if not has_active:
                Listing.objects.select_for_update().filter(id=listing_id).update(is_boosted=False, updated_at=now)
                listing_obj = Listing.objects.select_related('agent').filter(id=listing_id).first()
                if listing_obj and listing_obj.agent:
                    try:
                        from core.firebase import send_push_notification
                        send_push_notification(
                            user=listing_obj.agent,
                            title="Boost Ended",
                            body=f"The boost for your listing '{listing_obj.title}' has ended.",
                            data={
                                "type": "boost_ended",
                                "listing_id": str(listing_obj.id),
                            },
                            exclude_platforms=['ios'],
                        )
                    except Exception:
                        pass

    return count
