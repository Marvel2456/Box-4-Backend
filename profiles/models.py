from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid

class Plan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    max_listings = models.PositiveIntegerField(default=10, help_text="Maximum total listings allowed. Set to 0 for unlimited.")
    max_boosted = models.PositiveIntegerField(default=0, help_text="Maximum boosted listings allowed.")
    max_featured = models.PositiveIntegerField(default=0, help_text="Maximum featured listings allowed.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (${self.price})"


class BuyerProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='buyer_profile')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/buyers/', blank=True, null=True)
    
    # Location coordinates for nearest property calculations
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Geolocation address info
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    
    bio = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Buyer Profile of {self.user.email}"


class AgentProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='agent_profile')
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_profiles')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/agents/', blank=True, null=True)
    
    # Location coordinates
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Geolocation address info
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    
    bio = models.TextField(blank=True, null=True)
    
    # Agent-specific properties
    agency_name = models.CharField(max_length=150, blank=True, null=True)
    license_number = models.CharField(max_length=100, blank=True, null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"Agent Profile of {self.user.email}"


class AdminProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='admin_profile')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profiles/admins/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Admin Profile of {self.user.email}"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == 'buyer':
            BuyerProfile.objects.get_or_create(user=instance)
        elif instance.role == 'agent':
            AgentProfile.objects.get_or_create(user=instance)
        elif instance.role in ['admin', 'moderator']:
            AdminProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    if instance.role == 'buyer' and hasattr(instance, 'buyer_profile'):
        instance.buyer_profile.save()
    elif instance.role == 'agent' and hasattr(instance, 'agent_profile'):
        instance.agent_profile.save()
    elif instance.role in ['admin', 'moderator'] and hasattr(instance, 'admin_profile'):
        instance.admin_profile.save()


class AgentSubscription(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('due', 'Due'),
        ('cancelled', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, related_name='subscriptions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_started = models.DateTimeField(auto_now_add=True)
    next_renewal = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.agent.email} - {self.plan.name if self.plan else 'Plan'} ({self.status})"


class FeaturedPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    duration_days = models.PositiveIntegerField(default=7)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=5000.00)
    features = models.JSONField(default=list, blank=True, help_text="List of feature bullet points")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (N{self.price})"


class ListingFeature(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('due', 'Due'),
        ('cancelled', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey('agents.Listing', on_delete=models.CASCADE, related_name='featured_placements')
    featured_plan = models.ForeignKey(FeaturedPlan, on_delete=models.SET_NULL, null=True, related_name='listing_features')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date_started = models.DateTimeField(auto_now_add=True)
    date_due = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Feature: {self.listing.title} - {self.featured_plan.name if self.featured_plan else 'Plan'}"

