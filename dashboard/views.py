from django.shortcuts import render
from invoices.models import Invoice, Customer, Product
from django.db.models import Sum
from django.contrib.auth.decorators import login_required

@login_required(login_url='login')
def dashboard(request):
    total_invoices = Invoice.objects.count()

    total_customers = Customer.objects.count()

    total_products = Product.objects.count()

    total_revenue = (
        Invoice.objects.filter(is_paid=True)
        .aggregate(total=Sum('total'))['total']
        or 0
    )

    pending_amount = (
        Invoice.objects.filter(is_paid=False)
        .aggregate(total=Sum('total'))['total']
        or 0
    )

    recent_invoices = Invoice.objects.order_by('-date')[:5]

    low_stock_products = Product.objects.filter(quantity__lt=25)

    context = {
        'total_invoices': total_invoices,
        'total_customers': total_customers,
        'total_products': total_products,
        'total_revenue': total_revenue,
        'pending_amount': pending_amount,
        'recent_invoices': recent_invoices,
        'low_stock_products': low_stock_products,
    }

    return render(
        request,
        'dashboard/dashboard.html',
        context
    )


def home(request):
    return render(request,'dashboard/home.html')