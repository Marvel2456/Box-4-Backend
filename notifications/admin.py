from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Notification

class NotificationAdmin(ModelAdmin):
    list_display = ['recipient', 'sender', 'notification_type', 'title', 'is_read', 'created_at']
    search_fields = ['recipient__email', 'sender__email', 'title', 'message']
    list_filter = ['notification_type', 'is_read', 'created_at']


admin.site.register(Notification, NotificationAdmin)
