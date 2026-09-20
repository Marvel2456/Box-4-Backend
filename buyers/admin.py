from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import SavedListing, ListingView

class SavedListingAdmin(ModelAdmin):
    list_display = ['buyer', 'listing', 'created_at']
    search_fields = ['buyer__email', 'listing__title']
    list_filter = ['created_at']


class ListingViewAdmin(ModelAdmin):
    list_display = ['buyer', 'listing', 'created_at']
    search_fields = ['buyer__email', 'buyer__full_name', 'listing__title']
    list_filter = ['created_at']


admin.site.register(SavedListing, SavedListingAdmin)
admin.site.register(ListingView, ListingViewAdmin)
