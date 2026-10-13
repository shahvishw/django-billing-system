from django.contrib import admin

from .models import Invoice, InvoiceItem


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = (
        'invoice',
        'item_name',
        'quantity',
        'discount_percent',
        'mrp',
    )
    search_fields = (
        'invoice__invoice_number',
        'item_name',
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number',
        'organization',
        'customer',
        'date',
        'due_date',
        'total',
        'payment_status_display',
        'balance_due_display',
    )
    list_filter = (
        'date',
        'due_date',
    )
    search_fields = (
        'invoice_number',
        'customer__name',
    )
    list_select_related = (
        'organization',
        'customer',
    )

    @admin.display(
        description='Payment status',
        ordering='invoice_number',
    )
    def payment_status_display(self, invoice):
        return invoice.payment_status.replace('_', ' ').title()

    @admin.display(description='Balance due')
    def balance_due_display(self, invoice):
        return f'₹{invoice.balance_due}'