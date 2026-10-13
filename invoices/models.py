from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator

from customers.models import Customer
from organizations.models import Organization
from products.models import CatalogItem


class Invoice(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='invoices',
    )
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    invoice_number = models.CharField(max_length=20, unique=True)
    date = models.DateField(auto_now_add=True)
    due_date = models.DateField(null=True,blank=True)
    template_key = models.CharField(
        max_length=20,
        choices=Organization.InvoiceTemplate.choices,
        default=Organization.InvoiceTemplate.CLASSIC,
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
    )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_rate_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('18.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
    )
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_reminder_sent = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.invoice_number

    def clean(self):
        if (
            self.organization_id
            and self.customer_id
            and self.customer.organization_id != self.organization_id
        ):
            raise ValidationError(
                {'customer': 'Choose a customer from this organization.'}
            )

    @property
    def amount_paid(self):
        if hasattr(self, 'payment_total'):
            return self.payment_total or Decimal('0.00')

        return (
            self.payments.aggregate(total=Sum('amount'))['total']
            or Decimal('0.00')
        )


    @property
    def balance_due(self):
        return max(
            self.total - self.amount_paid,
            Decimal('0.00'),
        )


    @property
    def payment_status(self):
        if self.balance_due == Decimal('0.00'):
            return 'paid'

        if self.amount_paid > Decimal('0.00'):
            return 'partially_paid'

        if self.due_date and self.due_date < timezone.localdate():
            return 'overdue'

        return 'unpaid'


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice,
        related_name='items',
        on_delete=models.CASCADE,
    )
    catalog_item = models.ForeignKey(CatalogItem,on_delete=models.PROTECT)
    item_name = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    final_unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[
            MinValueValidator(Decimal('0.00')),
            MaxValueValidator(Decimal('100.00')),
        ],
    )

    def clean(self):
        if (
            self.invoice_id
            and self.catalog_item_id
            and self.invoice.organization_id != self.catalog_item.organization_id
        ):
            raise ValidationError(
                {'catalog_item': 'Choose an item from the invoice organization.'}
            )

    def get_total(self):
        return self.quantity * self.final_unit_price
