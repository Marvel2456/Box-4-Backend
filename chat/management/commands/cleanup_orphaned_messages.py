from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from chat.models import ChatRoom, Message

User = get_user_model()


class Command(BaseCommand):
    help = "Cleans up orphaned messages by linking them to appropriate ChatRooms and standardizing channel names."

    def handle(self, *args, **options):
        self.stdout.write("Starting cleanup of orphaned messages and channel names...")

        # 1. Standardize channel names
        updated_channels = 0
        for room in ChatRoom.objects.all():
            if not room.channel_name or room.channel_name.startswith('chatroom_'):
                room.channel_name = f"private-chat-{room.id}"
                room.save(update_fields=['channel_name'])
                updated_channels += 1

        self.stdout.write(f"Updated {updated_channels} chatroom channel names to standard format.")

        # 2. Backfill orphaned messages
        orphaned = Message.objects.filter(chatroom__isnull=True)
        orphaned_count = orphaned.count()
        self.stdout.write(f"Found {orphaned_count} orphaned messages.")

        fixed_count = 0
        for msg in orphaned:
            if not msg.sender_id or not msg.receiver_id:
                # Purge messages with missing sender or receiver
                msg.delete()
                continue

            room = ChatRoom.get_or_create_room(msg.sender, msg.receiver, msg.listing)
            msg.chatroom = room
            msg.save(update_fields=['chatroom'])
            fixed_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully processed {fixed_count} messages into ChatRooms."))
