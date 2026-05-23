from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'brand',
        'category',
        'price',
        'quantity'
    )

    list_filter = (
        'brand',
        'category'
    )

    search_fields = (
        'name',
        'brand',
        'category'
    )

   