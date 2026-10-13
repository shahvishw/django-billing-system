from decimal import Decimal
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from invoices.models import Invoice
from organizations.models import Membership, Organization
from audit.models import AuditLog

from .models import Payment


class PaymentAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='payment-owner',
            password='safe-test-password',
        )
        self.organization = Organization.objects.create(
            name='Payment Organization',
        )
        Membership.objects.create(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )

        self.other_organization = Organization.objects.create(
            name='Private Payment Organization',
        )

        customer = Customer.objects.create(
            organization=self.organization,
            name='Payment Customer',
            email='payment-customer@example.com',
            phone='9876543210',
            address='Payment address',
        )
        other_customer = Customer.objects.create(
            organization=self.other_organization,
            name='Private Payment Customer',
            email='private-payment-customer@example.com',
            phone='9999999999',
            address='Private payment address',
        )

        self.invoice = Invoice.objects.create(
            organization=self.organization,
            customer=customer,
            invoice_number='INV-PAYMENT-001',
            subtotal=Decimal('100.00'),
            tax=Decimal('18.00'),
            total=Decimal('118.00'),
        )
        self.other_invoice = Invoice.objects.create(
            organization=self.other_organization,
            customer=other_customer,
            invoice_number='INV-OTHER-PAY-001',
            subtotal=Decimal('100.00'),
            tax=Decimal('18.00'),
            total=Decimal('118.00'),
        )

    def login_as_owner(self):
        self.client.login(
            username='payment-owner',
            password='safe-test-password',
        )

    def test_anonymous_user_is_redirected_from_payment_page(self):
        response = self.client.get(
            reverse('make_payment', args=[self.invoice.pk]),
        )

        self.assertRedirects(
            response,
            (
                f"{reverse('login')}?next="
                f"{reverse('make_payment', args=[self.invoice.pk])}"
            ),
        )

    def test_other_organization_payment_url_returns_404(self):
        self.login_as_owner()

        response = self.client.get(
            reverse('make_payment', args=[self.other_invoice.pk]),
        )

        self.assertEqual(response.status_code, 404)

    def test_payment_is_assigned_to_active_organization(self):
        self.login_as_owner()

        response = self.client.post(
            reverse('make_payment', args=[self.invoice.pk]),
            {
                'amount': '50.00',
                'method': 'Cash',
                'received_on': '2026-09-25',
                'reference': 'CASH-001',
                'notes': 'First instalment',
            },
        )

        self.assertRedirects(
            response,
            reverse('invoice_detail', args=[self.invoice.pk]),
        )

        payment = Payment.objects.get(invoice=self.invoice)

        self.assertEqual(payment.organization, self.organization)
        self.assertEqual(payment.amount, Decimal('50.00'))
        self.assertEqual(payment.reference, 'CASH-001')
        self.assertEqual(
            self.invoice.payment_status,
            'partially_paid',
        )
        self.assertEqual(
            self.invoice.balance_due,
            Decimal('68.00'),
        )

    def test_invoice_can_have_multiple_payment_records(self):
        Payment.objects.create(
            organization=self.organization,
            invoice=self.invoice,
            amount=Decimal('40.00'),
            method='Cash',
            received_on=date(2026, 9, 25),
        )
        Payment.objects.create(
            organization=self.organization,
            invoice=self.invoice,
            amount=Decimal('78.00'),
            method='UPI',
            received_on=date(2026, 9, 25),
        )

        self.assertEqual(self.invoice.payments.count(), 2)
        self.assertEqual(
            self.invoice.amount_paid,
            Decimal('118.00'),
        )
        self.assertEqual(
            self.invoice.balance_due,
            Decimal('0.00'),
        )
        self.assertEqual(
            self.invoice.payment_status,
            'paid',
        )

    def test_invoice_reports_partial_payment_balance(self):
        Payment.objects.create(
            organization=self.organization,
            invoice=self.invoice,
            amount=Decimal('40.00'),
            method='Cash',
            received_on=date(2026, 9, 25),
        )

        self.assertEqual(
            self.invoice.amount_paid,
            Decimal('40.00'),
        )
        self.assertEqual(
            self.invoice.balance_due,
            Decimal('78.00'),
        )
        self.assertEqual(
            self.invoice.payment_status,
            'partially_paid',
        )

    def test_invoice_is_overdue_when_unpaid_after_due_date(self):
        self.invoice.due_date = date(2026, 9, 1)
        self.invoice.save(update_fields=['due_date'])

        self.assertEqual(
            self.invoice.payment_status,
            'overdue',
        )

    def test_full_payment_marks_invoice_as_paid_by_calculation(self):
        self.login_as_owner()

        response = self.client.post(
            reverse('make_payment', args=[self.invoice.pk]),
            {
                'amount': '118.00',
                'method': 'UPI',
                'received_on': '2026-09-25',
                'reference': 'UPI-001',
                'notes': '',
            },
        )

        self.assertRedirects(
            response,
            reverse('invoice_detail', args=[self.invoice.pk]),
        )

        self.assertEqual(
            self.invoice.payment_status,
            'paid',
        )
        self.assertEqual(
            self.invoice.balance_due,
            Decimal('0.00'),
        )

    def test_overpayment_is_rejected(self):
        self.login_as_owner()

        response = self.client.post(
            reverse('make_payment', args=[self.invoice.pk]),
            {
                'amount': '119.00',
                'method': 'Cash',
                'received_on': '2026-09-25',
                'reference': '',
                'notes': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Amount cannot exceed the remaining balance',
        )
        self.assertEqual(
            Payment.objects.filter(invoice=self.invoice).count(),
            0,
        )

    def test_payment_recording_is_added_to_audit_log(self):
        self.login_as_owner()

        self.client.post(
            reverse('make_payment', args=[self.invoice.pk]),
            {
                'amount': '50.00',
                'method': 'Cash',
                'received_on': '2026-09-25',
                'reference': 'AUDIT-001',
                'notes': '',
            },
        )

        self.assertTrue(
            AuditLog.objects.filter(
                organization=self.organization,
                actor=self.user,
                action=AuditLog.Action.PAYMENT_RECORDED,
                target_type='payment',
            ).exists()
        )