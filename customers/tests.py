from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from invoices.models import Invoice
from organizations.models import Membership, Organization
from audit.models import AuditLog

from .models import Customer
from .forms import normalize_phone


class CustomerAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='staff-user',
            password='safe-test-password',
        )
        self.organization = Organization.objects.create(
            name='Primary Organization',
        )
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )

        self.customer = Customer.objects.create(
            organization=self.organization,
            name='Test Customer',
            email='customer@example.com',
            phone='9876543210',
            address='Test address',
        )

        self.other_organization = Organization.objects.create(
            name='Other Organization',
        )
        self.other_customer = Customer.objects.create(
            organization=self.other_organization,
            name='Private Customer',
            email='private@example.com',
            phone='9999999999',
            address='Private address',
        )

    def login_as_user(self):
        self.client.login(
            username='staff-user',
            password='safe-test-password',
        )

    def test_anonymous_user_is_redirected_from_customer_create(self):
        response = self.client.get(reverse('customer_add'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('customer_add')}",
        )

    def test_customer_delete_requires_post(self):
        self.login_as_user()

        response = self.client.get(
            reverse('customer_delete', args=[self.customer.pk]),
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(
            Customer.objects.filter(pk=self.customer.pk).exists()
        )

    def test_customer_with_invoice_cannot_be_deleted(self):
        Invoice.objects.create(
            organization=self.organization,
            customer=self.customer,
            invoice_number='INV-TEST-001',
            subtotal=Decimal('100.00'),
            tax=Decimal('18.00'),
            total=Decimal('118.00'),
        )

        with self.assertRaises(ProtectedError):
            self.customer.delete()

    def test_customer_delete_view_keeps_customer_with_invoice_history(self):
        Invoice.objects.create(
            organization=self.organization,
            customer=self.customer,
            invoice_number='INV-TEST-002',
            subtotal=Decimal('100.00'),
            tax=Decimal('18.00'),
            total=Decimal('118.00'),
        )

        self.login_as_user()

        response = self.client.post(
            reverse('customer_delete', args=[self.customer.pk]),
            follow=True,
        )

        self.assertRedirects(response, reverse('customer_list'))
        self.assertTrue(
            Customer.objects.filter(pk=self.customer.pk).exists()
        )
        self.assertContains(
            response,
            'This customer cannot be deleted because invoice history exists.',
        )

    def test_customer_list_hides_other_organization_customers(self):
        self.login_as_user()

        response = self.client.get(reverse('customer_list'))

        self.assertContains(response, self.customer.name)
        self.assertNotContains(response, self.other_customer.name)

    def test_customer_create_assigns_active_organization(self):
        self.login_as_user()

        response = self.client.post(
            reverse('customer_add'),
            {
                'name': 'New Customer',
                'email': 'new-customer@example.com',
                'phone': '8888888888',
                'address': 'New address',
            },
        )

        self.assertRedirects(response, reverse('customer_list'))

        new_customer = Customer.objects.get(
            email='new-customer@example.com'
        )
        self.assertEqual(
            new_customer.organization,
            self.organization,
        )

    def test_customer_update_from_other_organization_returns_404(self):
        self.login_as_user()

        response = self.client.get(
            reverse('customer_edit', args=[self.other_customer.pk]),
        )

        self.assertEqual(response.status_code, 404)

    def test_customer_lookup_does_not_expose_other_organization_data(self):
        self.login_as_user()

        response = self.client.get(
            reverse('check_customer'),
            {
                'phone': self.other_customer.phone,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'exists': False})

    def test_customer_requires_organization(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Customer.objects.create(
                    name='Unassigned Customer',
                    email='unassigned@example.com',
                    phone='9876543210',
                    address='Test address',
                )

    def test_customer_creation_is_recorded_in_audit_log(self):
        self.login_as_user()

        self.client.post(
            reverse('customer_add'),
            {
                'name': 'Audited Customer',
                'email': 'audited-customer@example.com',
                'phone': '8888888888',
                'address': 'Audit address',
            },
        )

        self.assertTrue(
            AuditLog.objects.filter(
                organization=self.organization,
                actor=self.user,
                action=AuditLog.Action.CUSTOMER_CREATED,
                target_type='customer',
                description='Created customer Audited Customer.',
            ).exists()
        )

class PhoneNormalizationTests(TestCase):
    def test_valid_numbers_are_cleaned_to_one_standard_form(self):
        cases = {
            '9876543210': '9876543210',
            '98765 43210': '9876543210',
            '98765-43210': '9876543210',
            '(98765) 43210': '9876543210',
            '09876543210': '9876543210',
            '919876543210': '9876543210',
            '+91 98765 43210': '9876543210',
            '+91-98765-43210': '9876543210',
            '  9876543210  ': '9876543210',
            '+1 415 555 2671': '+14155552671',
            '+44 20 7946 0958': '+442079460958',
        }

        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_phone(raw), expected)

    def test_invalid_numbers_are_rejected(self):
        for raw in [
            '',
            'abcdefghij',
            '12345',
            '98765432101234',
            '9876543210x',
            '98765+43210',
            '+123',
            '+1234567890123456',
        ]:
            with self.subTest(raw=raw):
                with self.assertRaises(ValidationError):
                    normalize_phone(raw)


class CustomerIdentityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='identity-owner',
            password='safe-test-password',
        )
        self.organization = Organization.objects.create(name='Org A')
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        self.other_organization = Organization.objects.create(name='Org B')

        self.customer = Customer.objects.create(
            organization=self.organization,
            name='Existing Customer',
            email='shared@example.com',
            phone='9876543210',
            address='Existing address',
        )
        self.client.login(
            username='identity-owner',
            password='safe-test-password',
        )

    def valid_data(self, **changes):
        data = {
            'name': 'New Customer',
            'email': 'new@example.com',
            'phone': '8888888888',
            'address': 'New address',
        }
        data.update(changes)
        return data

    def make_other_customer(self, **fields):
        data = {
            'organization': self.other_organization,
            'name': 'Other Org Customer',
            'email': 'other@example.com',
            'phone': '7777777777',
            'address': 'Other address',
        }
        data.update(fields)
        return Customer.objects.create(**data)

    # ---- phone ----

    def test_same_phone_is_allowed_in_different_organizations(self):
        self.make_other_customer(phone='9876543210')

        self.assertEqual(
            Customer.objects.filter(phone='9876543210').count(),
            2,
        )

    def test_database_rejects_same_phone_in_same_organization(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Customer.objects.create(
                    organization=self.organization,
                    name='Duplicate',
                    phone='9876543210',
                    address='Duplicate address',
                )

    def test_create_stores_cleaned_phone(self):
        response = self.client.post(
            reverse('customer_add'),
            self.valid_data(phone='+91 88888-88888'),
        )

        self.assertRedirects(response, reverse('customer_list'))
        self.assertTrue(
            Customer.objects.filter(
                organization=self.organization,
                phone='8888888888',
            ).exists()
        )

    def test_duplicate_phone_in_another_format_shows_error_and_keeps_values(self):
        response = self.client.post(
            reverse('customer_add'),
            self.valid_data(phone='+91 98765 43210'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')
        self.assertContains(response, 'Existing Customer')
        self.assertContains(response, 'value="New Customer"')
        self.assertContains(response, 'value="+91 98765 43210"')
        self.assertEqual(
            Customer.objects.filter(name='New Customer').count(),
            0,
        )

    def test_invalid_phone_shows_visible_error(self):
        response = self.client.post(
            reverse('customer_add'),
            self.valid_data(phone='12345'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a valid phone number')

    def test_phone_is_required(self):
        response = self.client.post(
            reverse('customer_add'),
            self.valid_data(phone=''),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This field is required')

    def test_create_allows_phone_used_by_another_organization(self):
        self.make_other_customer(phone='8888888888')

        response = self.client.post(
            reverse('customer_add'),
            self.valid_data(phone='8888888888'),
        )

        self.assertRedirects(response, reverse('customer_list'))

    def test_editing_customer_can_keep_its_own_phone_and_email(self):
        response = self.client.post(
            reverse('customer_edit', args=[self.customer.pk]),
            self.valid_data(
                name='Renamed Customer',
                email='shared@example.com',
                phone='98765 43210',
            ),
        )

        self.assertRedirects(response, reverse('customer_list'))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, 'Renamed Customer')
        self.assertEqual(self.customer.phone, '9876543210')

    def test_editing_customer_cannot_take_another_customers_phone(self):
        second = Customer.objects.create(
            organization=self.organization,
            name='Second Customer',
            phone='7000000001',
            address='Second address',
        )

        response = self.client.post(
            reverse('customer_edit', args=[second.pk]),
            self.valid_data(email='', phone='9876543210'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')
        second.refresh_from_db()
        self.assertEqual(second.phone, '7000000001')

    # ---- email ----

    def test_customer_can_be_created_without_email(self):
        response = self.client.post(
            reverse('customer_add'),
            self.valid_data(email=''),
        )

        self.assertRedirects(response, reverse('customer_list'))
        self.assertTrue(
            Customer.objects.filter(
                organization=self.organization,
                name='New Customer',
                email='',
            ).exists()
        )

    def test_several_customers_without_email_are_allowed(self):
        Customer.objects.create(
            organization=self.organization,
            name='No Email One',
            phone='7000000001',
            address='Address',
        )
        Customer.objects.create(
            organization=self.organization,
            name='No Email Two',
            phone='7000000002',
            address='Address',
        )

        self.assertEqual(
            Customer.objects.filter(
                organization=self.organization,
                email='',
            ).count(),
            2,
        )

    def test_database_rejects_same_email_in_same_organization_ignoring_case(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Customer.objects.create(
                    organization=self.organization,
                    name='Duplicate',
                    email='SHARED@Example.com',
                    phone='7000000009',
                    address='Duplicate address',
                )

    def test_same_email_is_allowed_in_different_organizations(self):
        self.make_other_customer(email='shared@example.com')

        self.assertEqual(
            Customer.objects.filter(email='shared@example.com').count(),
            2,
        )

    def test_duplicate_email_shows_error_and_keeps_values(self):
        response = self.client.post(
            reverse('customer_add'),
            self.valid_data(email='Shared@Example.com'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')
        self.assertContains(response, 'value="Shared@Example.com"')
        self.assertEqual(
            Customer.objects.filter(name='New Customer').count(),
            0,
        )

    def test_invalid_email_shows_visible_error(self):
        response = self.client.post(
            reverse('customer_add'),
            self.valid_data(email='not-an-email'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'valid email')

    # ---- lookup used by the invoice form ----

    def test_lookup_finds_customer_by_phone_in_any_format(self):
        response = self.client.get(
            reverse('check_customer'),
            {'phone': '+91 98765-43210'},
        )

        data = response.json()
        self.assertTrue(data['exists'])
        self.assertEqual(data['customer_id'], str(self.customer.customer_id))
        self.assertEqual(data['name'], 'Existing Customer')

    def test_lookup_reports_missing_customer(self):
        response = self.client.get(
            reverse('check_customer'),
            {'phone': '6000000000'},
        )

        self.assertEqual(response.json(), {'exists': False})

    def test_lookup_reports_invalid_phone(self):
        response = self.client.get(
            reverse('check_customer'),
            {'phone': '123'},
        )

        data = response.json()
        self.assertFalse(data['exists'])
        self.assertIn('valid phone number', data['error'])