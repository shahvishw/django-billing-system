from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from payments.models import Payment
from customers.models import Customer
from invoices.models import Invoice
from organizations.models import Membership, Organization
from products.models import Product


class DashboardTenantTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dashboard-owner',
            password='safe-test-password',
        )
        self.staff = User.objects.create_user(
            username='dashboard-staff',
            password='safe-test-password',
        )
        self.accountant = User.objects.create_user(
            username='dashboard-accountant',
            password='safe-test-password',
        )
        self.organization = Organization.objects.create(
            name='Dashboard Organization',
        )
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        Membership.objects.create(
            user=self.staff,
            organization=self.organization,
            role=Membership.Role.STAFF,
        )
        Membership.objects.create(
            user=self.accountant,
            organization=self.organization,
            role=Membership.Role.ACCOUNTANT,
        )
        self.other_organization = Organization.objects.create(
            name='Private Dashboard Organization',
        )

        self.customer = Customer.objects.create(
            organization=self.organization,
            name='Dashboard Customer',
            email='dashboard-customer@example.com',
            phone='9876543210',
            address='Dashboard address',
        )
        other_customer = Customer.objects.create(
            organization=self.other_organization,
            name='Private Dashboard Customer',
            email='private-dashboard-customer@example.com',
            phone='9999999999',
            address='Private dashboard address',
        )

        self.product = Product.objects.create(
            organization=self.organization,
            name='Dashboard Product',
            mrp=Decimal('100.00'),
            brand='InvoicePRO',
            category='Test',
            origin='India',
            stock_quantity=10,
            is_active=True,
        )
        self.other_product = Product.objects.create(
            organization=self.other_organization,
            name='Private Dashboard Product',
            mrp=Decimal('500.00'),
            brand='Private Brand',
            category='Test',
            origin='India',
            stock_quantity=5,
            is_active=True,
        )

        paid_invoice = Invoice.objects.create(
            organization=self.organization,
            customer=self.customer,
            invoice_number='INV-OWN-PAID-01',
            subtotal=Decimal('100.00'),
            tax=Decimal('18.00'),
            total=Decimal('118.00'),
        )

        Payment.objects.create(
            organization=self.organization,
            invoice=paid_invoice,
            amount=Decimal('118.00'),
            method='Cash',
        )


        Invoice.objects.create(
            organization=self.organization,
            customer=self.customer,
            invoice_number='INV-OWN-PEND-01',
            subtotal=Decimal('200.00'),
            tax=Decimal('36.00'),
            total=Decimal('236.00'),
        )

        other_paid_invoice = Invoice.objects.create(
            organization=self.other_organization,
            customer=other_customer,
            invoice_number='INV-OTHER-PAID-01',
            subtotal=Decimal('1000.00'),
            tax=Decimal('180.00'),
            total=Decimal('1180.00'),
        )

        Payment.objects.create(
            organization=self.other_organization,
            invoice=other_paid_invoice,
            amount=Decimal('1180.00'),
            method='UPI',
        )

    def login_as_owner(self):
        self.client.login(
            username='dashboard-owner',
            password='safe-test-password',
        )

    def test_anonymous_user_is_redirected_from_dashboard(self):
        response = self.client.get(reverse('dashboard'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('dashboard')}",
        )

    def test_dashboard_uses_only_active_organization_data(self):
        self.login_as_owner()

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_invoices'], 2)
        self.assertEqual(response.context['total_customers'], 1)
        self.assertEqual(response.context['total_products'], 1)
        self.assertEqual(
            response.context['total_revenue'],
            Decimal('118.00'),
        )
        self.assertEqual(
            response.context['pending_amount'],
            Decimal('236.00'),
        )

        recent_invoices = response.context['recent_invoices']
        low_stock_products = response.context['low_stock_products']

        self.assertTrue(
            all(
                invoice.organization == self.organization
                for invoice in recent_invoices
            )
        )
        self.assertEqual(
            list(low_stock_products),
            [self.product],
        )
        self.assertNotContains(
            response,
            'INV-OTHER-PAID-01',
        )
        self.assertNotContains(
            response,
            self.other_product.name,
        )
    def test_staff_dashboard_hides_revenue_metric(self):
        self.client.login(
            username='dashboard-staff',
            password='safe-test-password',
        )

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['can_view_revenue'])
        self.assertNotContains(response, 'Payments received')

    def test_accountant_dashboard_hides_inventory_panel(self):
        self.client.login(
            username='dashboard-accountant',
            password='safe-test-password',
        )

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['can_view_inventory'])
        self.assertNotContains(response, 'Low Stock Products')