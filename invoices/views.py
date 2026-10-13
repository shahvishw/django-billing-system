import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from organizations.models import Membership
from organizations.services import organization_required, role_required

from .models import Invoice
from .services import InvoiceCreationError, create_invoice
from .utils import InvoicePDFError, render_invoice_pdf, send_invoice_email

logger = logging.getLogger(__name__)

@login_required(login_url='login')
@organization_required
@role_required(
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
    Membership.Role.STAFF,
    Membership.Role.ACCOUNTANT,
)
def invoice_list(request):
    invoices = (
        Invoice.objects.filter(organization=request.organization)
        .select_related('customer')
        .annotate(payment_total=Sum('payments__amount'))
        .order_by('-date')
    )
    query = request.GET.get('q', '').strip()
    if query:
        invoices = invoices.filter(
            Q(invoice_number__icontains=query)
            | Q(customer__name__icontains=query)
        )

    status = request.GET.get('status', 'all')
    today = timezone.localdate()
    if status == 'paid':
        invoices = invoices.filter(
            Q(payment_total__gte=F('total')) | Q(total=0)
        )
    elif status == 'partially_paid':
        invoices = invoices.filter(payment_total__gt=0, payment_total__lt=F('total'))
    elif status == 'overdue':
        invoices = invoices.filter(
            due_date__lt=today,
            total__gt=0,
        ).filter(
            Q(payment_total__isnull=True) | Q(payment_total__lt=F('total'))
        )
    elif status == 'unpaid':
        invoices = invoices.filter(
            Q(payment_total__isnull=True) | Q(payment_total=0),
        ).filter(Q(due_date__isnull=True) | Q(due_date__gte=today), total__gt=0)
    else:
        status = 'all'

    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    parsed_from = parse_date(date_from) if date_from else None
    parsed_to = parse_date(date_to) if date_to else None
    if parsed_from:
        invoices = invoices.filter(date__gte=parsed_from)
    else:
        date_from = ''
    if parsed_to:
        invoices = invoices.filter(date__lte=parsed_to)
    else:
        date_to = ''

    page_obj = Paginator(invoices, 25).get_page(request.GET.get('page'))
    return render(
        request,
        'invoices/invoice_list.html',
        {
            'invoices': page_obj,
            'page_obj': page_obj,
            'query': query,
            'status': status,
            'date_from': date_from,
            'date_to': date_to,
        },
    )


@login_required(login_url='login')
@organization_required
@role_required(
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
    Membership.Role.STAFF,
)
@require_http_methods(["GET", "POST"])
def invoice_create(request):
    form_context = {
        'tax_rate': request.organization.tax_rate_percent / 100,
        'tax_percent': format(
            request.organization.tax_rate_percent, 'f'
        ).rstrip('0').rstrip('.'),
    }

    if request.method == 'POST':
        try:
            invoice = create_invoice(
                organization=request.organization,
                customer_id=request.POST.get('customer_id'),
                catalog_item_ids=request.POST.getlist('catalog_items[]'),
                quantities=request.POST.getlist('quantities[]'),
                discount_percentages=request.POST.getlist('discounts[]'),
                subtotal_discount_percent=request.POST.get('subtotal_discount', '0'),
                due_date=request.POST.get('due_date') or None,
                actor=request.user,
            )
        except InvoiceCreationError as error:
            messages.error(request, str(error))
            return render(
                request,
                'invoices/invoice_form.html',
                form_context,
                status=400,
            )

        organization = request.organization

        if organization.email_invoices_to_customers:
            if not invoice.customer.email:
                messages.info(
                    request,
                    'No email was sent because this customer has no email address.',
                )
            else:
                try:
                    email_sent = send_invoice_email(invoice)
                except Exception:
                    logger.exception(
                        'Invoice %s was created, but its email could not be sent.',
                        invoice.invoice_number,
                    )
                    messages.warning(
                        request,
                        'Invoice created successfully, but the email could not be sent.',
                    )
                else:
                    if not email_sent:
                        messages.warning(
                            request,
                            'Invoice created successfully, but email delivery is not configured.',
                        )

        return redirect('invoice_detail', pk=invoice.id)

    return render(request, 'invoices/invoice_form.html', form_context)

@login_required(login_url='login')
@organization_required
@role_required(
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
    Membership.Role.STAFF,
    Membership.Role.ACCOUNTANT,
)
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk,organization=request.organization)
    return render(request, 'invoices/invoice_detail.html', {'invoice': invoice})

@login_required(login_url='login')
@organization_required
@role_required(
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
    Membership.Role.STAFF,
    Membership.Role.ACCOUNTANT,
)
def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk,organization=request.organization)
    try:
        pdf_content = render_invoice_pdf(invoice)
    except InvoicePDFError:
        logger.exception(
            'Failed to generate PDF for invoice %s.',
            invoice.invoice_number,
        )
        return HttpResponse('Unable to generate this invoice PDF.', status=500)

    response = HttpResponse(pdf_content, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
    )

    return response
