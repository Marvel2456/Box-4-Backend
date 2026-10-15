import uuid
from django.db import models
from django.conf import settings


class PlatformPolicy(models.Model):
    """
    Stores platform legal terms and conditions and data protection / privacy policies.
    Configured by administrator from the admin dashboard.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_terms = models.TextField(
        blank=True,
        default='',
        help_text="Platform legal terms, terms of use, and conditions."
    )
    data_policy = models.TextField(
        blank=True,
        default='',
        help_text="Platform data policy, privacy policy, and user data protection terms."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_platform_policies'
    )

    class Meta:
        verbose_name = "Platform Legal & Data Policy"
        verbose_name_plural = "Platform Legal & Data Policies"
        ordering = ['-updated_at']

    def __str__(self):
        return f"Platform Policy (Last updated: {self.updated_at.strftime('%Y-%m-%d %H:%M')})"

    @classmethod
    def get_active_policy(cls):
        policy = cls.objects.first()
        if not policy:
            policy = cls.objects.create(
                legal_terms="Welcome to Box-4. By using our platform, you agree to our terms of service and legal conditions.",
                data_policy="Box-4 values your privacy. We securely collect, store, and process your data in accordance with our data protection policy."
            )
        return policy
