from django.core.mail import EmailMessage
from django.template.loader import get_template
from django.conf import settings
from pathlib import Path
from urllib.parse import unquote, urlparse
from xhtml2pdf import pisa
import io


class InvoicePDFError(Exception):
    """Raised when an invoice cannot be rendered into a valid PDF."""


def render_invoice_pdf(invoice):
    try:
        template = get_template('invoices/invoice_pdf.html')
        html = template.render({'invoice': invoice})
        pdf_file = io.BytesIO()
        result = pisa.CreatePDF(
            html,
            dest=pdf_file,
            link_callback=pdf_link_callback,
        )
        if result.err:
            raise InvoicePDFError('The invoice PDF could not be rendered.')
        content = pdf_file.getvalue()
        if not content.startswith(b'%PDF-'):
            raise InvoicePDFError('The invoice PDF output was incomplete.')
        return content
    except InvoicePDFError:
        raise
    except Exception as error:
        raise InvoicePDFError('The invoice PDF could not be rendered.') from error


def _email_delivery_configured():
    """Avoid reporting console or dummy backend mail as customer delivery."""
    return settings.EMAIL_BACKEND not in {
        'django.core.mail.backends.console.EmailBackend',
        'django.core.mail.backends.dummy.EmailBackend',
    }


def pdf_link_callback(uri, relative_path):
    parsed_uri = urlparse(uri)
    media_path = parsed_uri.path

    if media_path.startswith(settings.MEDIA_URL):
        relative_media_path = media_path.removeprefix(
            settings.MEDIA_URL
        )

        media_root = Path(settings.MEDIA_ROOT).resolve()
        local_path = (media_root / unquote(relative_media_path)).resolve()
        if not local_path.is_relative_to(media_root):
            raise ValueError('PDF media paths must stay inside MEDIA_ROOT.')
        return str(local_path)

    # Fonts and page-background images that ship with the PDF templates.
    if media_path.startswith(settings.STATIC_URL):
        pdf_assets = (Path(settings.BASE_DIR) / 'static' / 'pdf').resolve()
        relative_static_path = media_path.removeprefix(settings.STATIC_URL)
        local_path = (
            Path(settings.BASE_DIR) / 'static' / unquote(relative_static_path)
        ).resolve()
        if not local_path.is_relative_to(pdf_assets):
            raise ValueError('PDFs may only load files from static/pdf.')
        return str(local_path)

    raise ValueError(
        'PDFs may only load files from the media directory or static/pdf.'
    )

def send_invoice_email(invoice):
    if not invoice.customer.email or not _email_delivery_configured():
        return False
    pdf_content = render_invoice_pdf(invoice)

    email = EmailMessage(
        subject=f'Invoice {invoice.invoice_number}',
        body='Please find attached your invoice.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[invoice.customer.email]
    )

    email.attach(
        f'invoice_{invoice.invoice_number}.pdf',
        pdf_content,
        'application/pdf'
    )

    return email.send() == 1

def send_payment_reminder(invoice):
    if not invoice.customer.email or not _email_delivery_configured():
        return False
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
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[invoice.customer.email]
    )

    return email.send() == 1
