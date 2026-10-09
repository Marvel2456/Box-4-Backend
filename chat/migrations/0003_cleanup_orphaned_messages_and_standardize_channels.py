from django.db import migrations


def link_orphaned_messages_and_standardize_channels(apps, schema_editor):
    ChatRoom = apps.get_model('chat', 'ChatRoom')
    Message = apps.get_model('chat', 'Message')

    # 1. Standardize existing chatroom channel names
    for room in ChatRoom.objects.all():
        if not room.channel_name or room.channel_name.startswith('chatroom_'):
            room.channel_name = f"private-chat-{room.id}"
            room.save(update_fields=['channel_name'])

    # 2. Backfill any messages without a chatroom
    orphaned_messages = Message.objects.filter(chatroom__isnull=True)
    for msg in orphaned_messages:
        if not msg.sender_id or not msg.receiver_id:
            continue

        # Look for existing room between sender and receiver
        rooms = ChatRoom.objects.filter(participants=msg.sender).filter(participants=msg.receiver)
        if msg.listing_id:
            listing_room = rooms.filter(listing_id=msg.listing_id).first()
            room = listing_room or rooms.first()
        else:
            room = rooms.first()

        if not room:
            channel_name = f"private-chat-{msg.sender_id}_{msg.receiver_id}"
            room = ChatRoom.objects.create(
                listing_id=msg.listing_id,
                channel_name=channel_name
            )
            room.participants.add(msg.sender, msg.receiver)
            # Update to standard UUID-based channel name
            room.channel_name = f"private-chat-{room.id}"
            room.save(update_fields=['channel_name'])

        msg.chatroom = room
        msg.save(update_fields=['chatroom'])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0002_message_is_read_message_read_at_chatroom_and_more'),
    ]

    operations = [
        migrations.RunPython(link_orphaned_messages_and_standardize_channels, reverse_noop),
    ]
