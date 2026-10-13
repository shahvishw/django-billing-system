from rest_framework import serializers

from customers.models import Customer
from invoices.models import Invoice, InvoiceItem
from payments.models import Payment
from products.models import CatalogItem


class CustomerSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ('customer_id', 'name', 'email', 'phone')
        read_only_fields = fields


class CustomerSerializer(CustomerSummarySerializer):
    class Meta(CustomerSummarySerializer.Meta):
        fields = CustomerSummarySerializer.Meta.fields + (
            'address',
            'created_at',
        )
        read_only_fields = fields


class CatalogItemSerializer(serializers.ModelSerializer):
    sale_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        allow_null=True,
        read_only=True,
    )

    class Meta:
        model = CatalogItem
        fields = (
            'product_id',
            'item_type',
            'name',
            'brand',
            'category',
            'origin',
            'mrp',
            'sale_price',
            'default_discount_percent',
            'max_discount_percent',
            'stock_quantity',
            'is_active',
            'created_at',
        )
        read_only_fields = fields


class InvoiceItemSerializer(serializers.ModelSerializer):
    catalog_item_id = serializers.UUIDField(read_only=True)
    line_total = serializers.DecimalField(
        source='get_total',
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = InvoiceItem
        fields = (
            'catalog_item_id',
            'item_name',
            'quantity',
            'mrp',
            'final_unit_price',
            'discount_percent',
            'line_total',
        )
        read_only_fields = fields


class InvoiceSerializer(serializers.ModelSerializer):
    customer = CustomerSummarySerializer(read_only=True)
    items = InvoiceItemSerializer(many=True, read_only=True)
    amount_paid = serializers.ReadOnlyField()
    balance_due = serializers.ReadOnlyField()
    payment_status = serializers.ReadOnlyField()

    class Meta:
        model = Invoice
        fields = (
            'id',
            'invoice_number',
            'customer',
            'date',
            'due_date',
            'template_key',
            'subtotal',
            'discount_percent',
            'discount_amount',
            'tax_rate_percent',
            'tax',
            'total',
            'amount_paid',
            'balance_due',
            'payment_status',
            'items',
        )
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(
        source='invoice.invoice_number',
        read_only=True,
    )

    class Meta:
        model = Payment
        fields = (
            'id',
            'invoice_id',
            'invoice_number',
            'amount',
            'method',
            'received_on',
            'reference',
            'notes',
            'paid_at',
        )
        read_only_fields = fields
