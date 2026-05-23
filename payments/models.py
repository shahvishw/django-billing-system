from django.db import models
from invoices.models import Invoice

class Payment(models.Model):
    PAYMENT_METHODS = (
        ('Cash', 'Cash'),
        ('UPI', 'UPI'),
        ('Card', 'Card'),
    )

    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE)
    method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    paid_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment for {self.invoice.invoice_number}"
