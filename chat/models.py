from django.db import models
from django.conf import settings
from agents.models import Listing
import uuid


class ChatRoom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='chatrooms'
    )
    listing = models.ForeignKey(
        Listing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chatrooms'
    )
    channel_name = models.CharField(max_length=255, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def save(self, *args, **kwargs):
        if not self.channel_name:
            self.channel_name = f"private-chat-{self.id}"
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create_room(cls, user1, user2, listing=None):
        """
        Find an existing 1-on-1 chatroom between user1 and user2, or create a new one.
        """
        rooms = cls.objects.filter(participants=user1).filter(participants=user2)
        if listing:
            listing_rooms = rooms.filter(listing=listing)
            if listing_rooms.exists():
                return listing_rooms.first()
        
        room = rooms.first()
        if not room:
            room = cls.objects.create(listing=listing)
            room.participants.add(user1, user2)
            if not room.channel_name:
                room.channel_name = f"private-chat-{room.id}"
                room.save(update_fields=['channel_name'])
        else:
            if listing and not room.listing:
                room.listing = listing
                room.save(update_fields=['listing'])
        return room

    def __str__(self):
        return f"ChatRoom {self.channel_name} ({self.id})"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chatroom = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='messages',
        null=True,
        blank=True
    )
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
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def save(self, *args, **kwargs):
        if not self.chatroom_id and self.sender_id and self.receiver_id:
            room = ChatRoom.get_or_create_room(self.sender, self.receiver, self.listing)
            self.chatroom = room
        if self.chatroom and self.listing and not self.chatroom.listing:
            self.chatroom.listing = self.listing
            self.chatroom.save(update_fields=['listing'])
        if self.chatroom and not self.listing and self.chatroom.listing:
            self.listing = self.chatroom.listing
        super().save(*args, **kwargs)
        if self.chatroom:
            ChatRoom.objects.filter(id=self.chatroom.id).update(updated_at=self.timestamp if self.timestamp else models.functions.Now())

    def __str__(self):
        return f"From {self.sender.email} to {self.receiver.email} at {self.timestamp}"


class BlockedUser(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocked_users'
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocked_by_users'
    )
    reason = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['blocker', 'blocked'], name='unique_user_block')
        ]

    def __str__(self):
        return f"{self.blocker.email} blocked {self.blocked.email}"
