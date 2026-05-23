from django.shortcuts import render, redirect
from .models import Invoice, InvoiceItem
from customers.models import Customer
from .forms import InvoiceForm
from decimal import Decimal
from products.models import Product
import uuid
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.contrib.auth.decorators import login_required
from .utils import send_invoice_email


@login_required(login_url='login')
def invoice_list(request):
    invoices = Invoice.objects.all().order_by('-date')
    return render(request, 'invoices/invoice_list.html', {'invoices': invoices})


@login_required(login_url='login')
def invoice_create(request):
    if request.method == 'POST':

        # ================= CUSTOMER =================
        customer_id = request.POST.get('customer_id')

        if customer_id:
            customer = get_object_or_404(Customer, customer_id=customer_id)
        else:
            # Create new customer
            customer = Customer.objects.create(
                name=request.POST.get('cust-name'),
                email=request.POST.get('cust-email'),
                phone=request.POST.get('cust-phone'),
                address=request.POST.get('cust-address'),
            )

        # ================= INVOICE =================
        invoice = Invoice.objects.create(
            customer=customer,
            invoice_number=f"INV-{uuid.uuid4().hex[:6].upper()}"
        )

        # ================= PRODUCTS =================
        product_ids = request.POST.getlist('products[]')
        quantities = request.POST.getlist('quantities[]')

        subtotal = Decimal('0.00')

        for pid, qty in zip(product_ids, quantities):
            product = get_object_or_404(Product, product_id = pid)
            qty = int(qty)

            # Backend stock validation
            if qty > product.quantity:
                raise ValueError("Insufficient stock")

            line_total = product.price * qty
            subtotal += line_total

            InvoiceItem.objects.create(
                invoice=invoice,
                product=product,
                quantity=qty,
                price=product.price
            )

            # Reduce stock
            product.quantity -= qty
            product.save()

        # ================= TOTALS =================
        tax = subtotal * Decimal('0.18')
        total = subtotal + tax

        invoice.subtotal = subtotal
        invoice.tax = tax
        invoice.total = total
        invoice.save()

        # ================= EMAIL =================
        send_invoice_email(invoice)

        return redirect('invoice_detail', pk=invoice.id)

    return render(request, 'invoices/invoice_form.html')


def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    return render(request, 'invoices/invoice_detail.html', {'invoice': invoice})

def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    template = get_template('invoices/invoice_pdf.html')
    html = template.render({'invoice': invoice})

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'filename=invoice_{invoice.invoice_number}.pdf'

    pisa.CreatePDF(html, dest=response)
    return response 

