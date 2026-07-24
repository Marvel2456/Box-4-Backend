from django.db import models
from django.conf import settings
from agents.models import Listing
import uuid

class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_messages'
    )
    listing = models.ForeignKey(
        Listing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_messages'
    )
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"From {self.sender.email} to {self.receiver.email} at {self.timestamp}"
