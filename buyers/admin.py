from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import SavedListing

class SavedListingAdmin(ModelAdmin):
    list_display = ['buyer', 'listing', 'created_at']
    search_fields = ['buyer__email', 'listing__title']


admin.site.register(SavedListing, SavedListingAdmin)
