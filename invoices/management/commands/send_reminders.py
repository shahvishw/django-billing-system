from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from invoices.models import Invoice
from invoices.utils import send_payment_reminder


class Command(BaseCommand):
    help = 'Send payment reminders for invoices with an outstanding balance'

    def handle(self, *args, **kwargs):
        today = timezone.localdate()

        invoices = (
            Invoice.objects
            .filter(organization__send_payment_reminders=True)
            .exclude(customer__email='')
            .select_related('customer')
            .prefetch_related('payments')
        )

        for invoice in invoices:
            if invoice.payment_status == 'paid':
                continue

            reminder_start_date = (
                invoice.due_date
                or invoice.date + timedelta(days=45)
            )

            if not invoice.last_reminder_sent:
                if today >= reminder_start_date:
                    self.send_reminder(invoice, today)
            elif today >= invoice.last_reminder_sent + timedelta(days=15):
                self.send_reminder(invoice, today)

    def send_reminder(self, invoice, today):
        if not send_payment_reminder(invoice):
            self.stderr.write(
                f'Reminder not sent for invoice {invoice.invoice_number}; '
                'check outbound email configuration.'
            )
            return False

        invoice.last_reminder_sent = today
        invoice.save(update_fields=['last_reminder_sent'])
        return True
