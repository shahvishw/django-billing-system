from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.db import transaction

from audit.models import AuditLog
from audit.services import log_action
from invoices.models import Invoice
from organizations.models import Membership
from organizations.services import organization_required, role_required

from .forms import PaymentForm


@login_required(login_url='login')
@organization_required
@role_required(
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
    Membership.Role.STAFF,
    Membership.Role.ACCOUNTANT,
)
@require_http_methods(['GET', 'POST'])
def make_payment(request, invoice_id):
    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        organization=request.organization,
    )

    if invoice.payment_status == 'paid':
        messages.info(
            request,
            'This invoice has already been paid in full.',
        )
        return redirect('invoice_detail', pk=invoice.id)

    form = PaymentForm(
        request.POST or None,
        invoice=invoice,
        initial={
            'amount': invoice.balance_due,
        },
    )

    payment = None

    if form.is_valid():
        with transaction.atomic():
            invoice = Invoice.objects.select_for_update().get(
                pk=invoice.pk,
                organization=request.organization,
            )

            if form.cleaned_data['amount'] > invoice.balance_due:
                form.add_error(
                    'amount',
                    f'Amount cannot exceed the remaining balance of '
                    f'₹{invoice.balance_due}.',
                )
            else:
                payment = form.save(commit=False)
                payment.organization = request.organization
                payment.invoice = invoice
                payment.save()

                log_action(
                    organization=request.organization,
                    actor=request.user,
                    action=AuditLog.Action.PAYMENT_RECORDED,
                    target_type='payment',
                    target_id=payment.pk,
                    description=(
                        f'Recorded payment of ₹{payment.amount} '
                        f'for invoice {invoice.invoice_number}.'
                    ),
                )

    if payment is not None:
        messages.success(request, 'Payment recorded successfully.')
        return redirect('invoice_detail', pk=invoice.id)



    return render(
        request,
        'payments/payment_form.html',
        {
            'form': form,
            'invoice': invoice,
        },
    )
