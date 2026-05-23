from django.core.management.base import BaseCommand
from django.utils.timezone import now
from datetime import timedelta
from invoices.models import Invoice
from invoices.utils import send_payment_reminder

class Command(BaseCommand):
    help = 'Send payment reminders for unpaid invoices'

    def handle(self, *args, **kwargs):
        today = now().date()

        invoices = Invoice.objects.filter(is_paid=False)

        for invoice in invoices:
            invoice_date = invoice.date

            if not invoice.last_reminder_sent:
                if today >= invoice_date + timedelta(days=45):
                    send_payment_reminder(invoice)
                    invoice.last_reminder_sent = today
                    invoice.save()
            else:
                if today >= invoice.last_reminder_sent + timedelta(days=15):
                    send_payment_reminder(invoice)
                    invoice.last_reminder_sent = today
                    invoice.save()
