from rest_framework import serializers


class CatalogItemLookupSerializer(serializers.Serializer):
    """Fields the invoice editor needs for catalog search results."""

    catalog_item_id = serializers.UUIDField(source='product_id')
    name = serializers.CharField()
    brand = serializers.CharField()
    item_type = serializers.CharField()
    mrp = serializers.FloatField(allow_null=True)
    default_discount_percent = serializers.FloatField()
    max_discount_percent = serializers.FloatField()
    stock = serializers.SerializerMethodField()

    def get_stock(self, item):
        if item.item_type == 'product':
            return item.stock_quantity
        return None
