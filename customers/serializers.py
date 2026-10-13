from rest_framework import serializers


class CustomerLookupResponseSerializer(serializers.Serializer):
    """Stable JSON representation returned by the customer lookup endpoint."""

    exists = serializers.BooleanField()
    error = serializers.CharField(required=False)
    customer_id = serializers.UUIDField(required=False)
    name = serializers.CharField(required=False)
