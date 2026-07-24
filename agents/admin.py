from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline
from .models import Listing, ListingImage

class ListingImageInline(TabularInline):
    model = ListingImage
    extra = 1


class ListingAdmin(ModelAdmin):
    list_display = ['title', 'agent', 'category', 'price', 'is_published', 'is_boosted', 'is_featured', 'created_at']
    list_filter = ['category', 'is_published', 'is_boosted', 'is_featured']
    search_fields = ['title', 'agent__email', 'address']
    inlines = [ListingImageInline]


class ListingImageAdmin(ModelAdmin):
    list_display = ['id', 'listing', 'is_cover', 'created_at']
    list_filter = ['is_cover', 'created_at']
    search_fields = ['listing__title', 'listing__agent__email']


admin.site.register(Listing, ListingAdmin)
admin.site.register(ListingImage, ListingImageAdmin)
