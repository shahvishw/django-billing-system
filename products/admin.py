from django.contrib import admin

from .models import CatalogItem


@admin.register(CatalogItem)
class CatalogItemAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'item_type',
        'brand',
        'category',
        'cost_price',
        'mrp',
        'default_discount_percent',
        'max_discount_percent',
        'stock_quantity',
        'is_active',
    )
    list_filter = (
        'item_type',
        'is_active',
        'brand',
        'category',
    )
    search_fields = (
        'name',
        'brand',
        'category',
    )