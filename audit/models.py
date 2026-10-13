from django.conf import settings
from django.db import models

from organizations.models import Organization


class AuditLog(models.Model):
    class Action(models.TextChoices):
        ORGANIZATION_CREATED = (
            'organization_created',
            'Organization created',
        )
        STAFF_CREATED = (
            'staff_created',
            'Staff account created',
        )
        STAFF_ROLE_CHANGED = (
            'staff_role_changed',
            'Staff role changed',
        )
        STAFF_DEACTIVATED = (
            'staff_deactivated',
            'Staff access deactivated',
        )
        STAFF_ACTIVATED = (
            'staff_activated',
            'Staff access activated',
        )
        CUSTOMER_CREATED = (
            'customer_created',
            'Customer created',
        )
        CUSTOMER_UPDATED = (
            'customer_updated',
            'Customer updated',
        )
        CUSTOMER_DELETED = (
            'customer_deleted',
            'Customer deleted',
        )
        CATALOG_ITEM_CREATED = (
            'catalog_item_created',
            'Catalog item created',
        )
        CATALOG_ITEM_UPDATED = (
            'catalog_item_updated',
            'Catalog item updated',
        )
        CATALOG_ITEM_STATUS_CHANGED = (
            'catalog_item_status_changed',
            'Catalog item status changed',
        )
        CATALOG_ITEM_DELETED = (
            'catalog_item_deleted',
            'Catalog item deleted',
        )
        INVOICE_CREATED = (
            'invoice_created',
            'Invoice created',
        )
        PAYMENT_RECORDED = (
            'payment_recorded',
            'Payment recorded',
        )
        ORGANIZATION_UPDATED = (
            'organization_updated',
            'Organization profile updated',
        )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='audit_logs',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(
        max_length=50,
        choices=Action.choices,
    )
    target_type = models.CharField(max_length=50)
    target_id = models.CharField(max_length=64)
    description = models.CharField(max_length=255,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['organization', '-created_at'],
            ),
        ]

    def __str__(self):
        return (
            f'{self.organization.name}: '
            f'{self.get_action_display()}'
        )
