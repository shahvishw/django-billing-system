from decimal import Decimal

from django.conf import settings
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Q
from django.db.models.functions import Lower

class Organization(models.Model):
    class InvoiceTemplate(models.TextChoices):
        CLASSIC = 'classic', 'Classic'
        MODERN = 'modern', 'Modern'
        MINIMAL = 'minimal', 'Minimal'

    class DiscountMode(models.TextChoices):
        PER_ITEM = 'per_item', 'Discount on each product'
        SUBTOTAL = 'subtotal', 'Discount on subtotal'

    name = models.CharField(max_length=150)
    address = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=25, blank=True)
    tax_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Tax or business registration ID',
    )
    logo = models.ImageField(
        upload_to='organization_logos/',
        blank=True,
    )
    authorized_signature = models.ImageField(
        upload_to='organization_signatures/',
        blank=True,
        verbose_name='Authorized signature',
    )
    discount_mode = models.CharField(
        max_length=20,
        choices=DiscountMode.choices,
        default=DiscountMode.PER_ITEM,
        help_text='Controls whether invoice discounts are entered per product or on the subtotal.',
    )
    tax_rate_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('18.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
        verbose_name='Tax rate (%)',
        help_text='Total tax rate applied to the discounted invoice amount.',
    )
    invoice_template = models.CharField(
        max_length=20,
        choices=InvoiceTemplate.choices,
        default=InvoiceTemplate.CLASSIC,
    )
    email_invoices_to_customers = models.BooleanField(
        default=False,
        verbose_name='Email invoice PDF to customers',
        help_text='When on, a new invoice is emailed to the customer if they have an email address.',
    )
    send_payment_reminders = models.BooleanField(
        default=False,
        verbose_name='Send payment reminders',
        help_text='When on, overdue invoices are reminded by email if the customer has an email address.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner','Owner'
        MANAGER = 'manager','Manager'
        STAFF = 'staff','Staff'
        ACCOUNTANT = 'accountant','Accountant'

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organization_memberships'
    )
    login_username = models.CharField(
        max_length=150,
        blank=True,
        default='',
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STAFF,
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization__name', 'login_username', 'user__username']
        constraints = [
            models.UniqueConstraint(
                fields=['organization','user'],
                name='unique_membership_per_organization'
            ),
            models.UniqueConstraint(
                Lower('login_username'),
                'organization',
                condition=~Q(login_username=''),
                name='unique_login_username_per_organization',
            ),
        ]

    def __str__(self):
        return (
            f"{self.login_username or self.user.username} - "
            f"{self.organization.name} ({self.get_role_display()})"
        )

    
