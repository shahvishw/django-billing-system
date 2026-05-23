from django.core.mail import EmailMessage
from django.template.loader import get_template
from django.conf import settings
from xhtml2pdf import pisa
import io

def send_invoice_email(invoice):
    template = get_template('invoices/invoice_pdf.html')
    html = template.render({'invoice': invoice})

    pdf_file = io.BytesIO()
    pisa.CreatePDF(html, dest=pdf_file)

    email = EmailMessage(
        subject=f'Invoice {invoice.invoice_number}',
        body='Please find attached your invoice.',
        from_email=settings.EMAIL_HOST_USER,
        to=[invoice.customer.email]
    )

    email.attach(
        f'invoice_{invoice.invoice_number}.pdf',
        pdf_file.getvalue(),
        'application/pdf'
    )

    email.send()


def send_payment_reminder(invoice):
    email = EmailMessage(
        subject='Payment Reminder',
        body=f'''
Dear {invoice.customer.name},

This is a reminder that payment for Invoice {invoice.invoice_number}
is still pending.

Total Amount: {invoice.total}

Please complete the payment at the earliest.

Thank you,
InvoicePro Team
''',
        from_email=settings.EMAIL_HOST_USER,
        to=[invoice.customer.email]
    )

    email.send()
