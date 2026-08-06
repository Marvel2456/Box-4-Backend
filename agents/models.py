from django.db import models
from django.conf import settings
import uuid

class Listing(models.Model):
    CATEGORY_CHOICES = (
        ('house', 'House'),
        ('apartment', 'Apartment'),
        ('lodge', 'Lodge'),
        ('mall', 'Mall'),
        ('hotel', 'Hotel'),
        ('villa', 'Villa'),
        ('condo', 'Condo'),
        ('shop', 'Shop'),
        ('land', 'Land'),
        ('bungalow', 'Bungalow'),
        ('plaza', 'Plaza'),
        ('duplex', 'Duplex'),
        ('multi_story_building', 'Multi-story Building'),
        ('single_flat', 'Single flat'),
        ('airbnb', 'Airbnb'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='listings',
        limit_choices_to={'role': 'agent'}
    )
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    
    # Location
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # Features
    bedrooms = models.PositiveIntegerField(default=0)
    bathrooms = models.PositiveIntegerField(default=0)
    balconies = models.PositiveIntegerField(default=0)
    total_rooms = models.PositiveIntegerField(default=0)
    
    # Environment / Facilities Tags
    facilities = models.JSONField(default=list, blank=True, help_text="List of environment/facilities tags e.g. ['Parking lot', 'Garden']")
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('pending', 'Pending Approval'),
        ('sold', 'Sold'),
        ('rejected', 'Rejected'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_published = models.BooleanField(default=True)
    is_boosted = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_reported = models.BooleanField(default=False)
    views_count = models.PositiveIntegerField(default=0, help_text="Number of views on this listing.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.category} (${self.price})"


from core.image_processing import process_and_convert_to_webp

class ListingImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='images', null=True, blank=True)
    image = models.ImageField(upload_to='listings/')
    is_cover = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.image and not self.image.name.lower().endswith('.webp'):
            self.image = process_and_convert_to_webp(self.image, max_dimension=1920, quality=88)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Image for {self.listing.title}"


class Report(models.Model):
    REPORT_TYPE_CHOICES = (
        ('listing', 'Reported Listing'),
        ('user', 'Reported User'),
        ('auto_fraud', 'Auto Fraud Flag'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES, default='listing')
    reason = models.CharField(max_length=255, default='Fake images')
    description = models.TextField(blank=True, null=True)

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, null=True, blank=True, related_name='reports')
    reported_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='reports_against')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='filed_reports')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Report ({self.report_type}) - {self.reason}"

