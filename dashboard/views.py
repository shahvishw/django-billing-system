from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import F, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from audit.models import AuditLog
from customers.models import Customer
from invoices.models import Invoice
from organizations.models import Membership
from organizations.services import organization_required, role_required
from payments.models import Payment
from products.models import Product


@login_required(login_url='login')
@organization_required
@role_required(
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
    Membership.Role.STAFF,
    Membership.Role.ACCOUNTANT,
)
def dashboard(request):
    role = request.membership.role

    invoice_query = Invoice.objects.filter(
        organization=request.organization,
    ).annotate(payment_total=Sum('payments__amount'))

    total_invoices = Invoice.objects.filter(
        organization=request.organization,
    ).count()

    pending_amount = sum(
        (
            max(total - (payment_total or Decimal('0.00')), Decimal('0.00'))
            for total, payment_total in invoice_query.order_by().values_list(
                'total',
                'payment_total',
            )
        ),
        Decimal('0.00'),
    )

    overdue_invoice_count = invoice_query.filter(
        due_date__lt=timezone.localdate(),
        total__gt=0,
    ).filter(
        Q(payment_total__isnull=True) | Q(payment_total__lt=F('total'))
    ).count()

    recent_invoices = list(
        invoice_query.select_related('customer').order_by('-date')[:5]
    )

    total_customers = Customer.objects.filter(
        organization=request.organization,
    ).count()

    total_products = Product.objects.filter(
        organization=request.organization,
    ).count()

    total_revenue = (
        Payment.objects.filter(
            organization=request.organization,
        )
        .aggregate(total=Sum('amount'))['total']
        or Decimal('0.00')
    )

    payment_count = Payment.objects.filter(
        organization=request.organization,
    ).count()

    can_view_revenue = role in (
        Membership.Role.OWNER,
        Membership.Role.MANAGER,
        Membership.Role.ACCOUNTANT,
    )

    can_view_inventory = role in (
        Membership.Role.OWNER,
        Membership.Role.MANAGER,
        Membership.Role.STAFF,
    )

    is_owner = role == Membership.Role.OWNER

    low_stock_products = Product.objects.none()

    if can_view_inventory:
        low_stock_products = Product.objects.filter(
            organization=request.organization,
            item_type=Product.ItemType.PRODUCT,
            stock_quantity__lt=25,
        ).order_by('stock_quantity', 'name')[:5]

    recent_activity = AuditLog.objects.none()

    if is_owner:
        recent_activity = (
            AuditLog.objects.filter(
                organization=request.organization,
            )
            .select_related('actor')[:5]
        )
        recent_actor_ids = [
            log.actor_id for log in recent_activity if log.actor_id
        ]
        recent_actor_names = dict(
            Membership.objects.filter(
                organization=request.organization,
                user_id__in=recent_actor_ids,
            ).values_list('user_id', 'login_username')
        )
        for log in recent_activity:
            log.actor_display = (
                recent_actor_names.get(log.actor_id)
                or (log.actor.username if log.actor else 'System')
            )

    metrics = []

    if role in (
        Membership.Role.OWNER,
        Membership.Role.MANAGER,
    ):
        metrics = [
            {
                'label': 'Payments received',
                'value': f'₹{total_revenue}',
                'icon': 'bi-currency-rupee',
                'style': 'revenue',
            },
            {
                'label': 'Outstanding balance',
                'value': f'₹{pending_amount}',
                'icon': 'bi-clock-history',
                'style': 'pending',
            },
            {
                'label': 'Total invoices',
                'value': total_invoices,
                'icon': 'bi-receipt',
                'style': 'invoice',
            },
            {
                'label': 'Total customers',
                'value': total_customers,
                'icon': 'bi-people',
                'style': 'customer',
            },
        ]

    elif role == Membership.Role.STAFF:
        metrics = [
            {
                'label': 'Organization invoices',
                'value': total_invoices,
                'icon': 'bi-receipt',
                'style': 'invoice',
            },
            {
                'label': 'Customers',
                'value': total_customers,
                'icon': 'bi-people',
                'style': 'customer',
            },
            {
                'label': 'Outstanding balance',
                'value': f'₹{pending_amount}',
                'icon': 'bi-clock-history',
                'style': 'pending',
            },
        ]

    elif role == Membership.Role.ACCOUNTANT:
        metrics = [
            {
                'label': 'Payments received',
                'value': f'₹{total_revenue}',
                'icon': 'bi-currency-rupee',
                'style': 'revenue',
            },
            {
                'label': 'Outstanding balance',
                'value': f'₹{pending_amount}',
                'icon': 'bi-clock-history',
                'style': 'pending',
            },
            {
                'label': 'Overdue invoices',
                'value': overdue_invoice_count,
                'icon': 'bi-exclamation-circle',
                'style': 'pending',
            },
            {
                'label': 'Payment records',
                'value': payment_count,
                'icon': 'bi-wallet2',
                'style': 'invoice',
            },
        ]

    quick_actions = [
        {
            'label': 'View invoices',
            'url_name': 'invoice_list',
            'icon': 'bi-receipt',
        },
        {
            'label': 'View customers',
            'url_name': 'customer_list',
            'icon': 'bi-people',
        },
    ]

    if role in (
        Membership.Role.OWNER,
        Membership.Role.MANAGER,
        Membership.Role.STAFF,
    ):
        quick_actions.insert(
            0,
            {
                'label': 'Create invoice',
                'url_name': 'invoice_add',
                'icon': 'bi-plus-circle',
            },
        )
        quick_actions.insert(
            1,
            {
                'label': 'Add customer',
                'url_name': 'customer_add',
                'icon': 'bi-person-plus',
            },
        )

    context = {
        'role': role,
        'is_owner': is_owner,
        'can_view_revenue': can_view_revenue,
        'can_view_inventory': can_view_inventory,
        'metrics': metrics,
        'quick_actions': quick_actions,
        'total_invoices': total_invoices,
        'total_customers': total_customers,
        'total_products': total_products,
        'total_revenue': total_revenue,
        'pending_amount': pending_amount,
        'overdue_invoice_count': overdue_invoice_count,
        'payment_count': payment_count,
        'recent_invoices': recent_invoices,
        'low_stock_products': low_stock_products,
        'recent_activity': recent_activity,
    }

    return render(
        request,
        'dashboard/dashboard.html',
        context,
    )


def home(request):
    return render(request, 'dashboard/home.html')
