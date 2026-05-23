from django.shortcuts import render, redirect, get_object_or_404
from .models import Customer
from .forms import CustomerForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

@login_required(login_url='login')
def customer_list(request):
    customers = Customer.objects.all()
    return render(request, 'customers/customer_list.html', {'customers': customers})


def customer_create(request):

    form = CustomerForm(
        request.POST or None
    )

    if form.is_valid():

        form.save()

        return redirect('customer_list')

    return render(
        request,
        'customers/customer_form.html',
        {
            'form': form,
            'customer': None
        }
    )

def customer_update(request, pk):

    customer = get_object_or_404(
        Customer,
        pk=pk
    )

    form = CustomerForm(
        request.POST or None,
        instance=customer
    )

    if form.is_valid():

        form.save()

        return redirect('customer_list')

    return render(
        request,
        'customers/customer_form.html',
        {
            'form': form,
            'customer': customer
        }
    )

def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    customer.delete()
    return redirect('customer_list')

def check_customer(request):
    name = request.GET.get('name')
    email = request.GET.get('email')

    try:
        customer = Customer.objects.get(name=name, email=email)
        return JsonResponse({
            'exists': True,
            'customer_id': customer.customer_id
        })
    except Customer.DoesNotExist:
        return JsonResponse({'exists': False})