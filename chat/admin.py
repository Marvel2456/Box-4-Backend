from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Message

class MessageAdmin(ModelAdmin):
    list_display = ['sender', 'receiver', 'listing', 'message', 'timestamp']
    search_fields = ['sender__email', 'receiver__email', 'message']


admin.site.register(Message, MessageAdmin)
