from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods, require_POST

from audit.models import AuditLog
from audit.services import log_action
from organizations.models import Membership
from organizations.services import organization_required, role_required

from .forms import CatalogItemForm
from .models import CatalogItem
from .serializers import CatalogItemLookupSerializer


@login_required(login_url='login')
@organization_required
@role_required(
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
    Membership.Role.STAFF,
)
def catalog_list(request):
    items = CatalogItem.objects.filter(
        organization=request.organization,
    ).annotate(
        usage_count=Count('invoiceitem'),
    ).order_by('name')
    query = request.GET.get('q', '').strip()
    if query:
        items = items.filter(name__icontains=query)

    item_type = request.GET.get('type', 'all')
    if item_type in (CatalogItem.ItemType.PRODUCT, CatalogItem.ItemType.SERVICE):
        items = items.filter(item_type=item_type)
    else:
        item_type = 'all'

    status = request.GET.get('status', 'all')
    if status == 'active':
        items = items.filter(is_active=True)
    elif status == 'inactive':
        items = items.filter(is_active=False)
    else:
        status = 'all'

    page_obj = Paginator(items, 25).get_page(request.GET.get('page'))
    return render(
        request,
        'products/catalog_list.html',
        {
            'items': page_obj,
            'page_obj': page_obj,
            'status': status,
            'item_type': item_type,
            'query': query,
        },
    )


@login_required(login_url='login')
@organization_required
@role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
@require_http_methods(['GET', 'POST'])
def catalog_create(request):
    form = CatalogItemForm(request.POST or None)

    if form.is_valid():
        with transaction.atomic():
            item = form.save(commit=False)
            item.organization = request.organization
            item.save()

            log_action(
                organization=request.organization,
                actor=request.user,
                action=AuditLog.Action.CATALOG_ITEM_CREATED,
                target_type='catalog_item',
                target_id=item.product_id,
                description=f'Created catalog item {item.name}.',
            )

        messages.success(request, 'Catalog item created.')
        return redirect('catalog_list')

    return render(
        request,
        'products/catalog_form.html',
        {'form': form, 'item': None},
    )


@login_required(login_url='login')
@organization_required
@role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
@require_http_methods(['GET', 'POST'])
def catalog_update(request, pk):
    item = get_object_or_404(
        CatalogItem,
        product_id=pk,
        organization=request.organization,
    )
    form = CatalogItemForm(request.POST or None, instance=item)

    if form.is_valid():
        with transaction.atomic():
            updated_item = form.save()
            log_action(
                organization=request.organization,
                actor=request.user,
                action=AuditLog.Action.CATALOG_ITEM_UPDATED,
                target_type='catalog_item',
                target_id=updated_item.product_id,
                description=f'Updated catalog item {updated_item.name}.',
            )

        messages.success(request, 'Catalog item updated.')
        return redirect('catalog_list')

    return render(
        request,
        'products/catalog_form.html',
        {'form': form, 'item': item},
    )


@login_required(login_url='login')
@organization_required
@role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
@require_POST
def catalog_toggle_active(request, pk):
    item = get_object_or_404(
        CatalogItem,
        product_id=pk,
        organization=request.organization,
    )
    item.is_active = not item.is_active

    with transaction.atomic():
        item.save(update_fields=['is_active'])
        log_action(
            organization=request.organization,
            actor=request.user,
            action=AuditLog.Action.CATALOG_ITEM_STATUS_CHANGED,
            target_type='catalog_item',
            target_id=item.product_id,
            description=(
                f'{"Activated" if item.is_active else "Deactivated"} '
                f'catalog item {item.name}.'
            ),
        )

    message = 'Catalog item activated.' if item.is_active else 'Catalog item deactivated.'
    messages.success(request, message)
    return redirect('catalog_list')


@login_required(login_url='login')
@organization_required
@role_required(Membership.Role.OWNER, Membership.Role.MANAGER)
@require_POST
def catalog_delete(request, pk):
    item = get_object_or_404(
        CatalogItem,
        product_id=pk,
        organization=request.organization,
    )
    item_name = item.name

    try:
        with transaction.atomic():
            item_id = item.product_id
            item.delete()
            log_action(
                organization=request.organization,
                actor=request.user,
                action=AuditLog.Action.CATALOG_ITEM_DELETED,
                target_type='catalog_item',
                target_id=item_id,
                description=f'Deleted catalog item {item_name}.',
            )
    except ProtectedError:
        messages.error(
            request,
            'This item is used by an invoice and cannot be deleted. Deactivate it instead.',
        )
    else:
        messages.success(request, 'Catalog item deleted.')

    return redirect('catalog_list')


@login_required(login_url='login')
@organization_required
@role_required(
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
    Membership.Role.STAFF,
)
@require_GET
def search_products(request):
    query = request.GET.get('q', '')

    products = CatalogItem.objects.filter(
        organization=request.organization,
        is_active=True,
        name__icontains=query,
    )[:10]

    data = CatalogItemLookupSerializer(products, many=True).data

    return JsonResponse(data, safe=False)
