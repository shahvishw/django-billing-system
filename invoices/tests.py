from django.contrib.auth.models import User

from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.utils import timezone
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from products.models import CatalogItem
from organizations.models import Membership, Organization
from audit.models import AuditLog

from .models import Invoice
from .services import InvoiceCreationError, create_invoice


class InvoiceAccessTests(TestCase):
    def test_anonymous_user_is_redirected_from_invoice_detail(self):
        response = self.client.get(
            reverse('invoice_detail', args=[999]),
        )

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('invoice_detail', args=[999])}",
        )

    def test_anonymous_user_is_redirected_from_invoice_pdf(self):
        response = self.client.get(
            reverse('invoice_pdf', args=[999]),
        )

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('invoice_pdf', args=[999])}",
        )


class InvoiceCreationServiceTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Invoice Organization',
        )

        self.other_organization = Organization.objects.create(
            name='Other Invoice Organization',
        )

        self.customer = Customer.objects.create(
            organization=self.organization,
            name='Invoice Test Customer',
            email='invoice-customer@example.com',
            phone='9876543210',
            address='Test address',
        )

        self.product = CatalogItem.objects.create(
            organization=self.organization,
            name='Test Product',
            mrp=Decimal('120.00'),
            brand='InvoicePRO',
            category='Test',
            origin='India',
            stock_quantity=10,
            is_active=True,
        )

        self.other_customer = Customer.objects.create(
            organization=self.other_organization,
            name='Other Customer',
            email='other-invoice-customer@example.com',
            phone='9999999999',
            address='Other address',
        )

        self.other_product = CatalogItem.objects.create(
            organization=self.other_organization,
            name='Other Product',
            mrp=Decimal('100.00'),
            brand='Other Brand',
            category='Test',
            origin='India',
            stock_quantity=10,
            is_active=True,
        )

    def test_creates_invoice_with_one_product_unit(self):
        invoice = create_invoice(
            organization=self.organization,
            customer_id=str(self.customer.customer_id),
            catalog_item_ids=[str(self.product.product_id)],
            quantities=['1'],
        )

        self.product.refresh_from_db()

        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(invoice.subtotal, Decimal('120.00'))
        self.assertEqual(invoice.tax, Decimal('21.60'))
        self.assertEqual(invoice.total, Decimal('141.60'))
        self.assertEqual(invoice.items.count(), 1)
        self.assertEqual(invoice.items.first().quantity, 1)
        self.assertEqual(self.product.stock_quantity, 9)

    def test_rejects_invoice_without_items(self):
        with self.assertRaises(InvoiceCreationError):
            create_invoice(
                organization=self.organization,
                customer_id=str(self.customer.customer_id),
                catalog_item_ids=[],
                quantities=[],
            )

        self.assertEqual(Invoice.objects.count(), 0)

    def test_insufficient_stock_creates_no_invoice_and_changes_no_stock(self):
        with self.assertRaises(InvoiceCreationError):
            create_invoice(
                organization=self.organization,
                customer_id=str(self.customer.customer_id),
                catalog_item_ids=[str(self.product.product_id)],
                quantities=['11'],
            )

        self.product.refresh_from_db()

        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(self.product.stock_quantity, 10)

    def test_duplicate_product_rows_cannot_oversell_stock(self):
        with self.assertRaises(InvoiceCreationError):
            create_invoice(
                organization=self.organization,
                customer_id=str(self.customer.customer_id),
                catalog_item_ids=[
                    str(self.product.product_id),
                    str(self.product.product_id),
                ],
                quantities=['6', '6'],
            )

        self.product.refresh_from_db()

        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(self.product.stock_quantity, 10)

    def test_inactive_product_cannot_be_invoiced(self):
        self.product.is_active = False
        self.product.save(update_fields=['is_active'])

        with self.assertRaises(InvoiceCreationError):
            create_invoice(
                organization=self.organization,
                customer_id=str(self.customer.customer_id),
                catalog_item_ids=[str(self.product.product_id)],
                quantities=['1'],
            )

        self.assertEqual(Invoice.objects.count(), 0)

    def test_customer_from_another_organization_cannot_be_invoiced(self):
        with self.assertRaises(InvoiceCreationError):
            create_invoice(
                organization=self.organization,
                customer_id=str(self.other_customer.customer_id),
                catalog_item_ids=[str(self.product.product_id)],
                quantities=['1'],
            )

        self.assertEqual(Invoice.objects.count(), 0)


    def test_product_from_another_organization_cannot_be_invoiced(self):
        with self.assertRaises(InvoiceCreationError):
            create_invoice(
                organization=self.organization,
                customer_id=str(self.customer.customer_id),
                catalog_item_ids=[str(self.other_product.product_id)],
                quantities=['1'],
            )

        self.assertEqual(Invoice.objects.count(), 0)

    def test_service_can_be_invoiced_without_stock(self):
        service = CatalogItem.objects.create(
            organization=self.organization,
            item_type=CatalogItem.ItemType.SERVICE,
            name='Website Consulting',
            mrp=Decimal('500.00'),
        )

        invoice = create_invoice(
            organization=self.organization,
            customer_id=str(self.customer.customer_id),
            catalog_item_ids=[str(service.product_id)],
            quantities=['2'],
        )

        service.refresh_from_db()
        invoice_item = invoice.items.get()

        self.assertEqual(service.stock_quantity, 0)
        self.assertEqual(invoice_item.catalog_item, service)
        self.assertEqual(invoice_item.item_name, 'Website Consulting')
        self.assertEqual(invoice.subtotal, Decimal('1000.00'))


    def test_invoice_keeps_item_name_when_catalog_item_is_renamed(self):
        invoice = create_invoice(
            organization=self.organization,
            customer_id=str(self.customer.customer_id),
            catalog_item_ids=[str(self.product.product_id)],
            quantities=['1'],
        )

        self.product.name = 'Renamed Product'
        self.product.save(update_fields=['name'])

        invoice_item = invoice.items.get()

        self.assertEqual(invoice_item.item_name, 'Test Product')
        self.assertEqual(invoice_item.catalog_item.name, 'Renamed Product')

    def test_invoice_creation_with_actor_is_recorded_in_audit_log(self):
        actor = User.objects.create_user(
            username='invoice-audit-user',
            password='safe-test-password',
        )

        invoice = create_invoice(
            organization=self.organization,
            customer_id=str(self.customer.customer_id),
            catalog_item_ids=[str(self.product.product_id)],
            quantities=['1'],
            actor=actor,
        )

        self.assertTrue(
            AuditLog.objects.filter(
                organization=self.organization,
                actor=actor,
                action=AuditLog.Action.INVOICE_CREATED,
                target_type='invoice',
                target_id=str(invoice.pk),
            ).exists()
        )

    def test_invoice_keeps_organization_template_choice(self):
        self.organization.invoice_template = (
            Organization.InvoiceTemplate.MODERN
        )
        self.organization.save(
            update_fields=['invoice_template'],
        )

        invoice = create_invoice(
            organization=self.organization,
            customer_id=str(self.customer.customer_id),
            catalog_item_ids=[str(self.product.product_id)],
            quantities=['1'],
        )

        self.assertEqual(
            invoice.template_key,
            Organization.InvoiceTemplate.MODERN,
        )

    def test_invoice_uses_mrp_as_discount_base(self):
        self.product.max_discount_percent = Decimal('20.00')
        self.product.save(update_fields=['max_discount_percent'])

        invoice = create_invoice(
            organization=self.organization,
            customer_id=str(self.customer.customer_id),
            catalog_item_ids=[str(self.product.product_id)],
            quantities=['2'],
            discount_percentages=['10'],
        )

        item = invoice.items.get()
        self.assertEqual(item.mrp, Decimal('120.00'))
        self.assertEqual(item.final_unit_price, Decimal('108.00'))
        self.assertEqual(item.get_total(), Decimal('216.00'))

    def test_subtotal_discount_is_applied_before_tax(self):
        self.organization.discount_mode = Organization.DiscountMode.SUBTOTAL
        self.organization.save(update_fields=['discount_mode'])

        second_product = CatalogItem.objects.create(
            organization=self.organization,
            name='Second Product',
            mrp=Decimal('200.00'),
            stock_quantity=20,
            is_active=True,
        )

        invoice = create_invoice(
            organization=self.organization,
            customer_id=str(self.customer.customer_id),
            catalog_item_ids=[str(self.product.product_id), str(second_product.product_id)],
            quantities=['10', '12'],
            subtotal_discount_percent='50',
        )

        self.assertEqual(invoice.subtotal, Decimal('3600.00'))
        self.assertEqual(invoice.discount_percent, Decimal('50.00'))
        self.assertEqual(invoice.discount_amount, Decimal('1800.00'))
        self.assertEqual(invoice.tax, Decimal('324.00'))
        self.assertEqual(invoice.total, Decimal('2124.00'))

    def test_per_item_discount_does_not_create_invoice_level_discount(self):
        self.product.max_discount_percent = Decimal('10.00')
        self.product.save(update_fields=['max_discount_percent'])

        invoice = create_invoice(
            organization=self.organization,
            customer_id=str(self.customer.customer_id),
            catalog_item_ids=[str(self.product.product_id)],
            quantities=['1'],
            discount_percentages=['10'],
        )

        self.assertEqual(invoice.discount_percent, Decimal('0.00'))
        self.assertEqual(invoice.discount_amount, Decimal('0.00'))
        self.assertEqual(invoice.subtotal, Decimal('108.00'))

    def test_invoice_applies_allowed_discount(self):
        self.product.max_discount_percent = Decimal('10.00')
        self.product.save(
            update_fields=['max_discount_percent'],
        )

        invoice = create_invoice(
            organization=self.organization,
            customer_id=str(self.customer.customer_id),
            catalog_item_ids=[str(self.product.product_id)],
            quantities=['1'],
            discount_percentages=['10'],
        )

        invoice_item = invoice.items.get()

        self.assertEqual(
            invoice_item.mrp,
            Decimal('120.00'),
        )
        self.assertEqual(
            invoice_item.discount_percent,
            Decimal('10.00'),
        )
        self.assertEqual(
            invoice_item.final_unit_price,
            Decimal('108.00'),
        )
        self.assertEqual(
            invoice.subtotal,
            Decimal('108.00'),
        )
        self.assertEqual(
            invoice.tax,
            Decimal('19.44'),
        )
        self.assertEqual(
            invoice.total,
            Decimal('127.44'),
        )

    def test_discount_above_catalog_limit_is_rejected(self):
        self.product.max_discount_percent = Decimal('5.00')
        self.product.save(
            update_fields=['max_discount_percent'],
        )

        with self.assertRaises(InvoiceCreationError):
            create_invoice(
                organization=self.organization,
                customer_id=str(self.customer.customer_id),
                catalog_item_ids=[
                    str(self.product.product_id),
                ],
                quantities=['1'],
                discount_percentages=['10'],
            )

        self.product.refresh_from_db()

        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(
            self.product.stock_quantity,
            10,
        )

class InvoiceTenantAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='invoice-owner',
            password='safe-test-password',
        )
        self.organization = Organization.objects.create(
            name='Invoice Owner Organization',
        )
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )

        self.other_organization = Organization.objects.create(
            name='Private Invoice Organization',
        )

        customer = Customer.objects.create(
            organization=self.organization,
            name='Visible Customer',
            email='visible-customer@example.com',
            phone='9876543210',
            address='Visible address',
        )
        other_customer = Customer.objects.create(
            organization=self.other_organization,
            name='Private Customer',
            email='private-invoice-customer@example.com',
            phone='9999999999',
            address='Private address',
        )

        self.invoice = Invoice.objects.create(
            organization=self.organization,
            customer=customer,
            invoice_number='INV-VISIBLE-001',
            subtotal=Decimal('100.00'),
            tax=Decimal('18.00'),
            total=Decimal('118.00'),
        )
        self.other_invoice = Invoice.objects.create(
            organization=self.other_organization,
            customer=other_customer,
            invoice_number='INV-PRIVATE-001',
            subtotal=Decimal('100.00'),
            tax=Decimal('18.00'),
            total=Decimal('118.00'),
        )

    def login_as_owner(self):
        self.client.login(
            username='invoice-owner',
            password='safe-test-password',
        )

    def test_invoice_list_hides_other_organization_invoices(self):
        self.login_as_owner()

        response = self.client.get(reverse('invoice_list'))

        self.assertContains(response, self.invoice.invoice_number)
        self.assertNotContains(
            response,
            self.other_invoice.invoice_number,
        )

    def test_other_organization_invoice_detail_returns_404(self):
        self.login_as_owner()

        response = self.client.get(
            reverse(
                'invoice_detail',
                args=[self.other_invoice.pk],
            ),
        )

        self.assertEqual(response.status_code, 404)

class InvoicePdfContentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='pdf-owner',
            password='safe-test-password',
        )
        self.organization = Organization.objects.create(
            name='PDF Test Organization',
        )
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        customer = Customer.objects.create(
            organization=self.organization,
            name='PDF Customer',
            email='pdf-customer@example.com',
            phone='9876543210',
            address='PDF address',
        )
        product = CatalogItem.objects.create(
            organization=self.organization,
            name='PDF Product',
            mrp=Decimal('100.00'),
            stock_quantity=10,
            is_active=True,
        )
        self.invoice = create_invoice(
            organization=self.organization,
            customer_id=str(customer.customer_id),
            catalog_item_ids=[str(product.product_id)],
            quantities=['2'],
        )

    def get_pdf_text(self):
        from io import BytesIO

        from pypdf import PdfReader

        self.client.login(
            username='pdf-owner',
            password='safe-test-password',
        )
        response = self.client.get(
            reverse('invoice_pdf', args=[self.invoice.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

        reader = PdfReader(BytesIO(response.content))
        return '\n'.join(page.extract_text() for page in reader.pages)

    def test_pdf_contains_no_stray_markup(self):
        text = self.get_pdf_text()

        self.assertNotIn('lass=', text)
        self.assertNotIn('</td>', text)
        self.assertNotIn('{{', text)

    def test_pdf_shows_item_and_correct_totals(self):
        text = self.get_pdf_text()

        self.assertIn('PDF Product', text)
        self.assertIn('200.00', text)   # 2 x 100.00 line total / subtotal
        self.assertIn('236.00', text)   # 200.00 + 18% tax

class InvoiceEmailSwitchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='switch-owner', password='safe-test-password'
        )
        self.organization = Organization.objects.create(name='Switch Org')
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        self.product = CatalogItem.objects.create(
            organization=self.organization,
            name='Switch Product',
            mrp=Decimal('100.00'),
            brand='B', category='C', origin='India',
            stock_quantity=10, is_active=True,
        )
        self.with_email = Customer.objects.create(
            organization=self.organization, name='Has Email',
            email='has-email@example.com', phone='9876543210', address='A',
        )
        self.no_email = Customer.objects.create(
            organization=self.organization, name='No Email',
            email='', phone='9876543211', address='A',
        )
        self.client.force_login(self.user)

    def _post_invoice(self, customer):
        return self.client.post(
            reverse('invoice_add'),
            {
                'customer_id': str(customer.customer_id),
                'catalog_items[]': [str(self.product.product_id)],
                'quantities[]': ['1'],
                'discounts[]': ['0'],
            },
        )

    def test_no_email_when_switch_off(self):
        with patch('invoices.views.send_invoice_email') as sender:
            self._post_invoice(self.with_email)
        sender.assert_not_called()
        self.assertEqual(Invoice.objects.count(), 1)

    def test_email_sent_when_switch_on_and_customer_has_email(self):
        self.organization.email_invoices_to_customers = True
        self.organization.save()
        with patch('invoices.views.send_invoice_email') as sender:
            self._post_invoice(self.with_email)
        sender.assert_called_once()

    def test_no_send_when_switch_on_but_customer_has_no_email(self):
        self.organization.email_invoices_to_customers = True
        self.organization.save()
        with patch('invoices.views.send_invoice_email') as sender:
            response = self._post_invoice(self.no_email)
        sender.assert_not_called()
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(response.status_code, 302)

    def test_helpers_return_false_without_email(self):
        from .utils import send_invoice_email, send_payment_reminder
        invoice = Invoice.objects.create(
            organization=self.organization, customer=self.no_email,
            invoice_number='INV-NOEMAIL-1',
            subtotal=Decimal('100.00'), tax=Decimal('18.00'), total=Decimal('118.00'),
        )
        self.assertFalse(send_invoice_email(invoice))
        self.assertFalse(send_payment_reminder(invoice))
        self.assertEqual(len(mail.outbox), 0)

    def _overdue_invoice(self, customer, number):
        return Invoice.objects.create(
            organization=self.organization, customer=customer,
            invoice_number=number,
            subtotal=Decimal('100.00'), tax=Decimal('18.00'), total=Decimal('118.00'),
            due_date=timezone.localdate() - timedelta(days=5),
        )

    def test_reminders_skipped_when_switch_off(self):
        self._overdue_invoice(self.with_email, 'INV-REM-OFF')
        call_command('send_reminders')
        self.assertEqual(len(mail.outbox), 0)

    def test_reminders_sent_only_for_customers_with_email_when_on(self):
        self.organization.send_payment_reminders = True
        self.organization.save()
        self._overdue_invoice(self.with_email, 'INV-REM-ON-1')
        self._overdue_invoice(self.no_email, 'INV-REM-ON-2')
        call_command('send_reminders')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['has-email@example.com'])

    def test_reminders_respect_each_organizations_switch(self):
        other = Organization.objects.create(name='Other Org')
        other_customer = Customer.objects.create(
            organization=other, name='Other', email='other@example.com',
            phone='9876543299', address='A',
        )
        Invoice.objects.create(
            organization=other, customer=other_customer,
            invoice_number='INV-OTHER-1',
            subtotal=Decimal('100.00'), tax=Decimal('18.00'), total=Decimal('118.00'),
            due_date=timezone.localdate() - timedelta(days=5),
        )
        self.organization.send_payment_reminders = True
        self.organization.save()
        self._overdue_invoice(self.with_email, 'INV-REM-MINE')
        call_command('send_reminders')
        recipients = [m.to[0] for m in mail.outbox]
        self.assertEqual(recipients, ['has-email@example.com'])