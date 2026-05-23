from django.contrib import admin
from .models import Invoice, InvoiceItem

admin.site.register(InvoiceItem)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number',
        'customer',
        'date',
        'total',
        'is_paid'
    )

    list_filter = (
        'is_paid',
        'date',
    )

    search_fields = (
        'invoice_number',
        'customer__name',
    )

