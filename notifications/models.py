from django.db import models
from django.conf import settings
from agents.models import Listing
import uuid

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('message', 'Message'),
        ('saved_listing', 'Saved Listing'),
        ('inquiry', 'Inquiry'),
        ('review', 'Review'),
        ('system', 'System'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sent_notifications'
    )
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, default='system')
    title = models.CharField(max_length=255)
    message = models.TextField()
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notification_type}] Notification for {self.recipient.email}: {self.title}"
