from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import ChatRoom, Message

class ChatRoomAdmin(ModelAdmin):
    list_display = ['id', 'channel_name', 'listing', 'created_at', 'updated_at']
    search_fields = ['channel_name', 'participants__email']
    filter_horizontal = ['participants']


class MessageAdmin(ModelAdmin):
    list_display = ['sender', 'receiver', 'chatroom', 'listing', 'is_read', 'read_at', 'timestamp']
    list_filter = ['is_read']
    search_fields = ['sender__email', 'receiver__email', 'message']


admin.site.register(ChatRoom, ChatRoomAdmin)
admin.site.register(Message, MessageAdmin)
