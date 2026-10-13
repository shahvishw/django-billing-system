import uuid
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from organizations.models import Organization

class Customer(models.Model):
    customer_id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name='customers',
    )
    name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=16)
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'phone'],
                name='unique_customer_phone_per_organization',
            ),
            models.UniqueConstraint(
                Lower('email'),
                'organization',
                condition=~Q(email=''),
                name='unique_customer_email_per_organization',
            ),
        ]

    def __str__(self):
        return self.name
