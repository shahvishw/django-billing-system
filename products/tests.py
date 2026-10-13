from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from invoices.models import Invoice, InvoiceItem
from organizations.models import Membership, Organization
from audit.models import AuditLog

from .models import CatalogItem

class ProductSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='staff-user',
            password='safe-test-password',
        )

        self.organization = Organization.objects.create(
            name='Product Organization',
        )
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )

        self.other_organization = Organization.objects.create(
            name='Other Product Organization',
        )

        self.active_product = CatalogItem.objects.create(
            organization=self.organization,
            name='Active Product',
            mrp='120.00',
            max_discount_percent='5.00',
            default_discount_percent='2.00',
            brand='InvoicePRO',
            category='Test',
            origin='India',
            stock_quantity=10,
            is_active=True,
        )
        self.inactive_product = CatalogItem.objects.create(
            organization=self.organization,
            name='Inactive Product',
            mrp='240.00',
            max_discount_percent='5.00',
            default_discount_percent='2.00',
            brand='InvoicePRO',
            category='Test',
            origin='India',
            stock_quantity=10,
            is_active=False,
        )

        self.other_organization_product = CatalogItem.objects.create(
            organization=self.other_organization,
            name='Private Product',
            mrp='360.00',
            max_discount_percent='5.00',
            default_discount_percent='2.00',
            brand='Private Brand',
            category='Test',
            origin='India',
            stock_quantity=10,
            is_active=True,
        )

    def test_anonymous_user_is_redirected_from_product_search(self):
        response = self.client.get(
            reverse('search_products'),
            {'q': 'Product'},
        )

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('search_products')}?q=Product",
        )

    def test_product_search_excludes_inactive_products(self):
        self.client.login(
            username='staff-user',
            password='safe-test-password',
        )

        response = self.client.get(
            reverse('search_products'),
            {'q': 'Product'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    'catalog_item_id': str(self.active_product.product_id),
                    'name': 'Active Product',
                    'brand': 'InvoicePRO',
                    'item_type': 'product',
                    'mrp': 120.0,
                    'default_discount_percent': 2.0,
                    'max_discount_percent': 5.0,
                    'stock': 10,
                }
            ],
        )

    def test_catalog_item_defaults_to_product_type(self):
        self.assertEqual(
            self.active_product.item_type,
            CatalogItem.ItemType.PRODUCT,
        )


    def test_service_catalog_item_can_have_zero_stock(self):
        service = CatalogItem.objects.create(
            organization=self.organization,
            item_type=CatalogItem.ItemType.SERVICE,
            name='Consulting Service',
            mrp='500.00',
        )

        self.assertEqual(service.stock_quantity, 0)
        self.assertTrue(service.is_active)

    def test_product_search_marks_services_without_stock(self):
        service = CatalogItem.objects.create(
            organization=self.organization,
            item_type=CatalogItem.ItemType.SERVICE,
            name='Consulting Service',
            mrp='500.00',
        )

        self.client.login(
            username='staff-user',
            password='safe-test-password',
        )

        response = self.client.get(
            reverse('search_products'),
            {'q': 'Consulting'},
        )

        self.assertEqual(
            response.json(),
            [
                {
                    'catalog_item_id': str(service.product_id),
                    'name': 'Consulting Service',
                    'brand': '',
                    'item_type': 'service',
                    'mrp': 500.0,
                    'default_discount_percent': 0.0,
                    'max_discount_percent': 0.0,
                    'stock': None,
                }
            ],
        )
    def test_product_search_does_not_expose_cost_price(self):
        self.active_product.cost_price = '60.00'
        self.active_product.save(
            update_fields=['cost_price'],
        )

        self.client.login(
            username='staff-user',
            password='safe-test-password',
        )

        response = self.client.get(
            reverse('search_products'),
            {'q': 'Active'},
        )

        self.assertNotIn(
            'cost_price',
            response.json()[0],
        )


class CatalogManagementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='catalog-owner', password='safe-test-password'
        )
        self.staff = User.objects.create_user(
            username='catalog-staff', password='safe-test-password'
        )
        self.organization = Organization.objects.create(name='Catalog Org')
        Membership.objects.create(
            user=self.owner,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        Membership.objects.create(
            user=self.staff,
            organization=self.organization,
            role=Membership.Role.STAFF,
        )
        self.item = CatalogItem.objects.create(
            organization=self.organization,
            name='Notebook',
            mrp='100.00',
            default_discount_percent='10.00',
            max_discount_percent='15.00',
            cost_price='50.00',
        )

    def login_as(self, user):
        self.client.force_login(user)

    def test_catalog_shows_sale_price_and_hides_cost_price(self):
        self.login_as(self.staff)

        response = self.client.get(reverse('catalog_list'))

        self.assertContains(response, '₹90.00')
        self.assertNotContains(response, '50.00')
        self.assertNotContains(response, reverse('catalog_edit', args=[self.item.product_id]))

    def test_owner_can_create_item_and_audit_it(self):
        self.login_as(self.owner)

        response = self.client.post(reverse('catalog_add'), {
            'item_type': 'product',
            'name': 'Pen',
            'cost_price': '5.00',
            'mrp': '10.00',
            'default_discount_percent': '0.00',
            'max_discount_percent': '5.00',
            'brand': '',
            'category': '',
            'origin': '',
            'stock_quantity': '20',
        })

        self.assertRedirects(response, reverse('catalog_list'))
        self.assertTrue(CatalogItem.objects.filter(organization=self.organization, name='Pen').exists())
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.CATALOG_ITEM_CREATED).exists())

    def test_owner_can_update_item(self):
        self.login_as(self.owner)

        response = self.client.post(reverse('catalog_edit', args=[self.item.product_id]), {
            'item_type': 'product',
            'name': 'Notebook Pro',
            'cost_price': '55.00',
            'mrp': '120.00',
            'default_discount_percent': '10.00',
            'max_discount_percent': '15.00',
            'brand': '',
            'category': '',
            'origin': '',
            'stock_quantity': '4',
        })

        self.assertRedirects(response, reverse('catalog_list'))
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, 'Notebook Pro')

    def test_owner_can_deactivate_and_reactivate_item(self):
        self.login_as(self.owner)
        url = reverse('catalog_toggle_active', args=[self.item.product_id])

        self.assertEqual(self.client.post(url).status_code, 302)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_active)

        self.client.post(url)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)

    def test_staff_cannot_change_catalog_items(self):
        self.login_as(self.staff)

        response = self.client.post(reverse('catalog_toggle_active', args=[self.item.product_id]))

        self.assertEqual(response.status_code, 403)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_active)

    def test_item_used_by_invoice_cannot_be_deleted(self):
        customer = Customer.objects.create(
            organization=self.organization,
            name='Invoice customer',
            phone='555001',
            address='Address',
        )
        invoice = Invoice.objects.create(
            organization=self.organization,
            customer=customer,
            invoice_number='CAT-001',
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            catalog_item=self.item,
            item_name=self.item.name,
            quantity=1,
            mrp=self.item.mrp,
            final_unit_price='90.00',
        )
        self.login_as(self.owner)

        response = self.client.post(reverse('catalog_delete', args=[self.item.product_id]))

        self.assertRedirects(response, reverse('catalog_list'))
        self.assertTrue(CatalogItem.objects.filter(pk=self.item.pk).exists())
        self.assertTrue(any('Deactivate it instead' in str(message) for message in get_messages(response.wsgi_request)))

    def test_catalog_list_is_scoped_to_active_organization(self):
        other_org = Organization.objects.create(name='Another Org')
        private_item = CatalogItem.objects.create(
            organization=other_org,
            name='Private item',
        )
        self.login_as(self.owner)

        response = self.client.get(reverse('catalog_list'))

        self.assertContains(response, self.item.name)
        self.assertNotContains(response, private_item.name)
