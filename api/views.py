from django.db.models import Q
from django.db.models import Sum
from django.db.models.functions import Coalesce
from decimal import Decimal
from rest_framework.authentication import SessionAuthentication
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from organizations.models import Membership

from .pagination import StandardResultsPagination
from .permissions import ActiveOrganizationPermission
from .serializers import (
    CatalogItemSerializer,
    CustomerSerializer,
    InvoiceSerializer,
    PaymentSerializer,
)
from customers.models import Customer
from invoices.models import Invoice
from payments.models import Payment
from products.models import CatalogItem


class OrganizationReadOnlyListView(generics.ListAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, ActiveOrganizationPermission]
    pagination_class = StandardResultsPagination
    allowed_roles = None


class OrganizationReadOnlyDetailView(generics.RetrieveAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, ActiveOrganizationPermission]
    allowed_roles = None


class CustomerListView(OrganizationReadOnlyListView):
    serializer_class = CustomerSerializer
    allowed_roles = (
        Membership.Role.OWNER,
        Membership.Role.MANAGER,
        Membership.Role.STAFF,
        Membership.Role.ACCOUNTANT,
    )

    def get_queryset(self):
        queryset = Customer.objects.filter(
            organization=self.request.organization,
        ).order_by('name')
        query = self.request.query_params.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(phone__icontains=query)
                | Q(email__icontains=query)
            )
        return queryset


class CustomerDetailView(OrganizationReadOnlyDetailView):
    serializer_class = CustomerSerializer
    lookup_field = 'customer_id'
    lookup_url_kwarg = 'pk'
    allowed_roles = CustomerListView.allowed_roles

    def get_queryset(self):
        return Customer.objects.filter(
            organization=self.request.organization,
        )


class CatalogItemListView(OrganizationReadOnlyListView):
    serializer_class = CatalogItemSerializer
    allowed_roles = (
        Membership.Role.OWNER,
        Membership.Role.MANAGER,
        Membership.Role.STAFF,
    )

    def get_queryset(self):
        queryset = CatalogItem.objects.filter(
            organization=self.request.organization,
        ).order_by('name')
        query = self.request.query_params.get('q', '').strip()
        item_type = self.request.query_params.get('type', '').strip()
        status = self.request.query_params.get('status', '').strip()
        if query:
            queryset = queryset.filter(name__icontains=query)
        if item_type in CatalogItem.ItemType.values:
            queryset = queryset.filter(item_type=item_type)
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        return queryset


class CatalogItemDetailView(OrganizationReadOnlyDetailView):
    serializer_class = CatalogItemSerializer
    lookup_field = 'product_id'
    lookup_url_kwarg = 'pk'
    allowed_roles = CatalogItemListView.allowed_roles

    def get_queryset(self):
        return CatalogItem.objects.filter(
            organization=self.request.organization,
        )


class InvoiceListView(OrganizationReadOnlyListView):
    serializer_class = InvoiceSerializer
    allowed_roles = (
        Membership.Role.OWNER,
        Membership.Role.MANAGER,
        Membership.Role.STAFF,
        Membership.Role.ACCOUNTANT,
    )

    def get_queryset(self):
        queryset = (
            Invoice.objects.filter(organization=self.request.organization)
            .select_related('customer')
            .prefetch_related('items')
            .annotate(
                payment_total=Coalesce(
                    Sum('payments__amount'),
                    Decimal('0.00'),
                )
            )
            .order_by('-date', '-pk')
        )
        query = self.request.query_params.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(invoice_number__icontains=query)
                | Q(customer__name__icontains=query)
            )
        return queryset


class InvoiceDetailView(OrganizationReadOnlyDetailView):
    serializer_class = InvoiceSerializer
    allowed_roles = InvoiceListView.allowed_roles

    def get_queryset(self):
        return (
            Invoice.objects.filter(organization=self.request.organization)
            .select_related('customer')
            .prefetch_related('items')
            .annotate(
                payment_total=Coalesce(
                    Sum('payments__amount'),
                    Decimal('0.00'),
                )
            )
        )


class PaymentListView(OrganizationReadOnlyListView):
    serializer_class = PaymentSerializer
    allowed_roles = InvoiceListView.allowed_roles

    def get_queryset(self):
        queryset = (
            Payment.objects.filter(organization=self.request.organization)
            .select_related('invoice')
        )
        query = self.request.query_params.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(invoice__invoice_number__icontains=query)
                | Q(reference__icontains=query)
            )
        return queryset


class PaymentDetailView(OrganizationReadOnlyDetailView):
    serializer_class = PaymentSerializer
    allowed_roles = PaymentListView.allowed_roles

    def get_queryset(self):
        return Payment.objects.filter(
            organization=self.request.organization,
        ).select_related('invoice')
