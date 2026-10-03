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
            self.channel_name = f"chatroom_{self.id}"
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
                room.channel_name = f"chatroom_{room.id}"
                room.save(update_fields=['channel_name'])
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
        super().save(*args, **kwargs)
        if self.chatroom:
            ChatRoom.objects.filter(id=self.chatroom.id).update(updated_at=self.timestamp if self.timestamp else models.functions.Now())

    def __str__(self):
        return f"From {self.sender.email} to {self.receiver.email} at {self.timestamp}"
