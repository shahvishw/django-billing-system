from django.shortcuts import render, redirect, get_object_or_404
from .models import Payment
from .forms import PaymentForm
from invoices.models import Invoice
from django.contrib.auth.decorators import login_required

@login_required(login_url='login')
def make_payment(request, invoice_id):
    invoice = get_object_or_404(Invoice, id=invoice_id)

    if invoice.is_paid:
        return redirect('invoice_detail', pk=invoice.id)

    form = PaymentForm(request.POST or None)
    if form.is_valid():
        payment = form.save(commit=False)
        payment.invoice = invoice
        payment.save()

        invoice.is_paid = True
        invoice.save()

        return redirect('invoice_detail', pk=invoice.id)

    return render(request, 'payments/payment_form.html', {
        'form': form,
        'invoice': invoice
    })
