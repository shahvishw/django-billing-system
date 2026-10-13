from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET,require_http_methods,require_POST
from django.db import transaction

from invoices.models import Invoice
from organizations.models import Membership
from organizations.services import organization_required, role_required

from audit.models import AuditLog
from audit.services import log_action

from django.core.exceptions import ValidationError

from .forms import CustomerForm, normalize_phone
from .models import Customer
from .serializers import CustomerLookupResponseSerializer


@login_required(login_url='login')
@organization_required
@role_required(
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
    Membership.Role.STAFF,
    Membership.Role.ACCOUNTANT
)
def customer_list(request):
    customers = Customer.objects.filter(
        organization=request.organization
    ).order_by('name')
    query = request.GET.get('q', '').strip()
    if query:
        customers = customers.filter(
            Q(name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
        )
    page_obj = Paginator(customers, 25).get_page(request.GET.get('page'))

    return render(
        request,
        'customers/customer_list.html',
        {'customers': page_obj, 'page_obj': page_obj, 'query': query},
    )


@login_required(login_url='login')
@organization_required
@role_required(
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
    Membership.Role.STAFF,
)
@require_http_methods(["GET", "POST"])
def customer_create(request):
    form = CustomerForm(
        request.POST or None,
       organization=request.organization,
   )

    if form.is_valid():
        with transaction.atomic():
            customer = form.save(commit=False)
            customer.organization = request.organization
            customer.save()

            log_action(
                organization=request.organization,
                actor=request.user,
                action=AuditLog.Action.CUSTOMER_CREATED,
                target_type='customer',
                target_id=customer.customer_id,
                description=(
                    f'Created customer {customer.name}.'
                ),
            )

        messages.success(request, 'Customer created successfully.')
        return redirect('customer_list')

    return render(
        request,
        'customers/customer_form.html',
        {
            'form': form,
            'customer': None,
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
def customer_update(request, pk):
    customer = get_object_or_404(
        Customer,
        pk=pk,
        organization=request.organization,
    )

    form = CustomerForm(
        request.POST or None,
       instance=customer,
       organization=request.organization,
   )

    if form.is_valid():
        with transaction.atomic():
            updated_customer = form.save()

            log_action(
                organization=request.organization,
                actor=request.user,
                action=AuditLog.Action.CUSTOMER_UPDATED,
                target_type='customer',
                target_id=updated_customer.customer_id,
                description=(
                    f'Updated customer {updated_customer.name}.'
                ),
            )

        messages.success(request, 'Customer updated successfully.')
        return redirect('customer_list')

    return render(
        request,
        'customers/customer_form.html',
        {
            'form': form,
            'customer': customer,
        },
    )


@login_required(login_url='login')
@organization_required
@role_required(
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
)
@require_POST
def customer_delete(request, pk):
    customer = get_object_or_404(
        Customer,
        pk=pk,
        organization=request.organization,
    )

    if Invoice.objects.filter(
        customer=customer,
        organization=request.organization,
    ).exists():
        messages.error(
            request,
            'This customer cannot be deleted because invoice history exists. '
            'Keep the record to preserve business history.',
        )
        return redirect('customer_list')

    customer_id = customer.customer_id
    customer_name = customer.name

    with transaction.atomic():
        customer.delete()

        log_action(
            organization=request.organization,
            actor=request.user,
            action=AuditLog.Action.CUSTOMER_DELETED,
            target_type='customer',
            target_id=customer_id,
            description=(
                f'Deleted customer {customer_name}.'
            ),
        )

    messages.success(request, 'Customer deleted successfully.')
    return redirect('customer_list')


@login_required(login_url='login')
@organization_required
@role_required(
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
    Membership.Role.STAFF,
)
@require_GET
def check_customer(request):
    try:
       phone = normalize_phone(request.GET.get('phone'))
    except ValidationError as error:
        payload = CustomerLookupResponseSerializer(
            {'exists': False, 'error': error.messages[0]}
        ).data
        return JsonResponse(payload)

    customer = Customer.objects.filter(
       phone=phone,
       organization=request.organization,
    ).first()

    if customer is None:
        payload = CustomerLookupResponseSerializer(
            {'exists': False}
        ).data
        return JsonResponse(payload)

    payload = CustomerLookupResponseSerializer(
        {
           'exists': True,
           'customer_id': customer.customer_id,
           'name': customer.name,
       }
    ).data
    return JsonResponse(payload)
