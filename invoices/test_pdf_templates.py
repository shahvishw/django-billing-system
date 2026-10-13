from decimal import Decimal

from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from organizations.models import Membership, Organization
from products.models import CatalogItem

from .services import create_invoice


class MoneyFilterTests(TestCase):
    def render(self, value, flt='inr'):
        return Template('{% load money %}{{ v|' + flt + ' }}').render(Context({'v': value}))

    def test_indian_grouping(self):
        self.assertEqual(self.render(Decimal('113988')), '₹1,13,988.00')
        self.assertEqual(self.render(Decimal('999.5')), '₹999.50')
        self.assertEqual(self.render(Decimal('12345678.9')), '₹1,23,45,678.90')

    def test_negative_empty_and_plain(self):
        self.assertEqual(self.render(Decimal('-1500')), '-₹1,500.00')
        self.assertEqual(self.render(None), '—')
        self.assertEqual(self.render(Decimal('1500'), 'inr_plain'), '1,500.00')


class InvoicePdfTemplateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('owner', password='pw-12345')
        self.org = Organization.objects.create(name='Acme Studio', address='1 Main Rd')
        Membership.objects.create(organization=self.org, user=self.user, role=Membership.Role.OWNER)
        self.customer = Customer.objects.create(
            organization=self.org, name='Jane Buyer', phone='9000000099', address='5 Side St',
        )
        self.item = CatalogItem.objects.create(
            organization=self.org, name='Logo design', item_type='service',
            mrp=Decimal('12000'), max_discount_percent=Decimal('20'), brand='Acme',
        )

    def make_invoice(self, template_key):
        self.org.invoice_template = template_key
        self.org.save()
        return create_invoice(
            organization=self.org, customer_id=str(self.customer.customer_id),
            catalog_item_ids=[str(self.item.product_id)], quantities=['2'],
            discount_percentages=['10'], actor=self.user,
        )

    def test_every_template_renders_a_pdf(self):
        self.client.login(username='owner', password='pw-12345')
        for key in ('classic', 'modern', 'minimal'):
            with self.subTest(template=key):
                invoice = self.make_invoice(key)
                self.assertEqual(invoice.template_key, key)
                response = self.client.get(reverse('invoice_pdf', args=[invoice.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.content.startswith(b'%PDF'))
                self.assertGreater(len(response.content), 5000)
