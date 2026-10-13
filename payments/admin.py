from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'invoice',
        'organization',
        'amount',
        'method',
        'received_on',
        'reference',
    )
    list_filter = (
        'method',
        'received_on',
    )
    search_fields = (
        'invoice__invoice_number',
        'reference',
    )
    list_select_related = (
        'invoice',
        'organization',
    )