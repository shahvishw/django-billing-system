from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from invoices.models import Invoice
from organizations.models import Organization


class Payment(models.Model):
    PAYMENT_METHODS = (
        ('Cash', 'Cash'),
        ('UPI', 'UPI'),
        ('Card', 'Card'),
        ('Bank Transfer', 'Bank Transfer'),
        ('Other', 'Other'),
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='payments',
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name='payments',
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.01')),
        ],
    )
    method = models.CharField(max_length=20,choices=PAYMENT_METHODS)
    received_on = models.DateField(default=timezone.localdate)
    reference = models.CharField(max_length=100,blank=True,)
    notes = models.TextField(blank=True)
    paid_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_on', '-paid_at']

    def clean(self):
        if (
            self.organization_id
            and self.invoice_id
            and self.invoice.organization_id != self.organization_id
        ):
            raise ValidationError(
                {'invoice': 'Choose an invoice from this organization.'}
            )

    def __str__(self):
        return (
            f'{self.invoice.invoice_number} - '
            f'₹{self.amount} ({self.received_on})'
        )
