from django.db import models
from django.conf import settings
from agents.models import Listing
import uuid

class SavedListing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_listings',
        limit_choices_to={'role': 'buyer'}
    )
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='saved_by_buyers'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('buyer', 'listing')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.buyer.email} saved {self.listing.title}"
