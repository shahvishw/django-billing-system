from decimal import Decimal
from io import BytesIO
from PIL import Image

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, RequestFactory
from django.http import HttpResponse

from customers.models import Customer
from invoices.models import Invoice
from products.models import CatalogItem
from audit.models import AuditLog

from .services import organization_required, role_required
from .models import Membership, Organization


User = get_user_model()

@organization_required
@role_required(
    Membership.Role.OWNER,
    Membership.Role.MANAGER,
)
def owner_or_manager_view(request):
    return HttpResponse('Allowed')


class OrganizationMembershipTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='organization-user',
            password='safe-test-password',
        )
        self.organization = Organization.objects.create(
            name='Test Organization',
        )

    def test_membership_defaults_to_staff_role(self):
        membership = Membership.objects.create(
            organization=self.organization,
            user=self.user,
        )

        self.assertEqual(
            membership.role,
            Membership.Role.STAFF,
        )

    def test_user_can_belong_to_multiple_organizations(self):
        second_organization = Organization.objects.create(
            name='Second Organization',
        )

        Membership.objects.create(
            organization=self.organization,
            user=self.user,
            role=Membership.Role.OWNER,
        )
        Membership.objects.create(
            organization=second_organization,
            user=self.user,
            role=Membership.Role.ACCOUNTANT,
        )

        self.assertEqual(
            self.user.organization_memberships.count(),
            2,
        )

    def test_duplicate_membership_is_not_allowed(self):
        Membership.objects.create(
            organization=self.organization,
            user=self.user,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Membership.objects.create(
                    organization=self.organization,
                    user=self.user,
                )

    def test_organization_with_customer_cannot_be_deleted(self):
        Customer.objects.create(
            organization=self.organization,
            name='Organization Customer',
            email='organization-customer@example.com',
            phone='9876543210',
            address='Test address',
        )

        with self.assertRaises(ProtectedError):
            self.organization.delete()


class RolePermissionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.organization = Organization.objects.create(
            name='Role Test Organization',
        )

        self.owner = User.objects.create_user(
            username='role-owner',
            password='safe-test-password',
        )
        self.staff = User.objects.create_user(
            username='role-staff',
            password='safe-test-password',
        )
        self.accountant = User.objects.create_user(
            username='role-accountant',
            password='safe-test-password',
        )

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
        Membership.objects.create(
            user=self.accountant,
            organization=self.organization,
            role=Membership.Role.ACCOUNTANT,
        )

    def build_request(self, user):
        request = self.factory.get('/')
        request.user = user
        request.session = {}
        return request

    def test_owner_can_access_owner_or_manager_action(self):
        response = owner_or_manager_view(
            self.build_request(self.owner)
        )

        self.assertEqual(response.status_code, 200)

    def test_staff_cannot_access_owner_or_manager_action(self):
        response = owner_or_manager_view(
            self.build_request(self.staff)
        )

        self.assertEqual(response.status_code, 403)

    def test_accountant_cannot_access_owner_or_manager_action(self):
        response = owner_or_manager_view(
            self.build_request(self.accountant)
        )

        self.assertEqual(response.status_code, 403)

class StaffManagementTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            username='organization-owner',
            password='safe-test-password',
        )
        self.manager = User.objects.create_user(
            username='organization-manager',
            password='safe-test-password',
        )
        self.other_owner = User.objects.create_user(
            username='other-owner',
            password='safe-test-password',
        )

        self.organization = Organization.objects.create(
            name='Owner Organization',
        )
        self.other_organization = Organization.objects.create(
            name='Other Organization',
        )

        Membership.objects.create(
            user=self.owner,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        Membership.objects.create(
            user=self.manager,
            organization=self.organization,
            role=Membership.Role.MANAGER,
        )
        Membership.objects.create(
            user=self.other_owner,
            organization=self.other_organization,
            role=Membership.Role.OWNER,
        )

    def login_as_owner(self):
        self.client.force_login(self.owner)

    def test_owner_can_create_staff_account(self):
        self.login_as_owner()

        response = self.client.post(
            reverse('staff_add'),
            data={
                'username': 'new-staff',
                'email': 'new-staff@example.com',
                'password1': 'StrongPassword123!',
                'password2': 'StrongPassword123!',
                'role': Membership.Role.STAFF,
            },
        )

        user = User.objects.get(username='new-staff')
        membership = Membership.objects.get(
            user=user,
            organization=self.organization,
        )

        self.assertRedirects(response, reverse('staff_list'))
        self.assertEqual(membership.role, Membership.Role.STAFF)
        self.assertTrue(membership.is_active)

        audit_log = AuditLog.objects.get(
            action=AuditLog.Action.STAFF_CREATED,
        )

        self.assertEqual(audit_log.actor, self.owner)
        self.assertEqual(audit_log.organization, self.organization)

    def test_manager_cannot_open_staff_management(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse('staff_list'))

        self.assertEqual(response.status_code, 403)

    def test_owner_can_deactivate_staff_member(self):
        staff_user = User.objects.create_user(
            username='leaving-staff',
            password='safe-test-password',
        )
        staff_membership = Membership.objects.create(
            user=staff_user,
            organization=self.organization,
            role=Membership.Role.STAFF,
        )

        self.login_as_owner()

        response = self.client.post(
            reverse('staff_deactivate', args=[staff_membership.pk]),
        )

        staff_membership.refresh_from_db()

        self.assertRedirects(response, reverse('staff_list'))
        self.assertFalse(staff_membership.is_active)

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.STAFF_DEACTIVATED,
                actor=self.owner,
                organization=self.organization,
            ).exists()
        )

    def test_owner_cannot_deactivate_staff_from_another_organization(self):
        other_staff = User.objects.create_user(
            username='other-staff',
            password='safe-test-password',
        )
        other_membership = Membership.objects.create(
            user=other_staff,
            organization=self.other_organization,
            role=Membership.Role.STAFF,
        )

        self.login_as_owner()

        response = self.client.post(
            reverse('staff_deactivate', args=[other_membership.pk]),
        )

        other_membership.refresh_from_db()

        self.assertEqual(response.status_code, 404)
        self.assertTrue(other_membership.is_active)

class InactiveMembershipLoginTests(TestCase):
    def test_login_redirects_inactive_staff_to_access_page(self):
        user = User.objects.create_user(
            username='inactive-staff',
            password='safe-test-password',
        )
        organization = Organization.objects.create(
            name='Inactive Login Organization',
        )
        Membership.objects.create(
            user=user,
            organization=organization,
            role=Membership.Role.STAFF,
            is_active=False,
        )

        response = self.client.post(
            reverse('login'),
            data={
                'username': 'inactive-staff',
                'password': 'safe-test-password',
            },
        )

        self.assertRedirects(
            response,
            reverse('membership_inactive'),
        )

class BusinessRoutePermissionTests(TestCase):
    def setUp(self):
        self.organization = Organization.objects.create(
            name='Permission Test Organization',
        )

        self.owner = User.objects.create_user(
            username='permission-owner',
            password='safe-test-password',
        )
        self.manager = User.objects.create_user(
            username='permission-manager',
            password='safe-test-password',
        )
        self.staff = User.objects.create_user(
            username='permission-staff',
            password='safe-test-password',
        )
        self.accountant = User.objects.create_user(
            username='permission-accountant',
            password='safe-test-password',
        )

        for user, role in (
            (self.owner, Membership.Role.OWNER),
            (self.manager, Membership.Role.MANAGER),
            (self.staff, Membership.Role.STAFF),
            (self.accountant, Membership.Role.ACCOUNTANT),
        ):
            Membership.objects.create(
                user=user,
                organization=self.organization,
                role=role,
            )

        self.customer = Customer.objects.create(
            organization=self.organization,
            name='Permission Customer',
            email='permission-customer@example.com',
            phone='9876543210',
            address='Permission address',
        )

        self.catalog_item = CatalogItem.objects.create(
            organization=self.organization,
            name='Permission Product',
            mrp=Decimal('100.00'),
            stock_quantity=10,
        )

        self.invoice = Invoice.objects.create(
            organization=self.organization,
            customer=self.customer,
            invoice_number='PERM-001',
            total=Decimal('100.00'),
        )

    def get_as(self, user, url_name, *args):
        self.client.force_login(user)

        return self.client.get(
            reverse(url_name, args=args),
        )

    def test_manager_and_staff_can_use_sales_routes(self):
        for user in (self.manager, self.staff):
            self.assertEqual(
                self.get_as(user, 'customer_add').status_code,
                200,
            )
            self.assertEqual(
                self.get_as(user, 'invoice_add').status_code,
                200,
            )
            self.assertEqual(
                self.get_as(user, 'search_products').status_code,
                200,
            )

    def test_staff_cannot_delete_customer(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse('customer_delete', args=[self.customer.pk]),
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            Customer.objects.filter(pk=self.customer.pk).exists()
        )

    def test_accountant_has_financial_read_access_only(self):
        self.assertEqual(
            self.get_as(self.accountant, 'dashboard').status_code,
            200,
        )
        self.assertEqual(
            self.get_as(self.accountant, 'customer_list').status_code,
            200,
        )
        self.assertEqual(
            self.get_as(self.accountant, 'invoice_list').status_code,
            200,
        )
        self.assertEqual(
            self.get_as(
                self.accountant,
                'invoice_detail',
                self.invoice.pk,
            ).status_code,
            200,
        )
        self.assertEqual(
            self.get_as(
                self.accountant,
                'make_payment',
                self.invoice.pk,
            ).status_code,
            200,
        )

    def test_accountant_cannot_change_sales_or_search_products(self):
        self.assertEqual(
            self.get_as(self.accountant, 'customer_add').status_code,
            403,
        )
        self.assertEqual(
            self.get_as(self.accountant, 'invoice_add').status_code,
            403,
        )
        self.assertEqual(
            self.get_as(self.accountant, 'search_products').status_code,
            403,
        )

def create_test_image(filename):
    image = Image.new('RGB', (20, 20), color='white')
    image_bytes = BytesIO()
    image.save(image_bytes, format='PNG')

    return SimpleUploadedFile(
        filename,
        image_bytes.getvalue(),
        content_type='image/png',
    )

class OrganizationSettingsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='settings-owner',
            password='safe-test-password',
        )
        self.staff = User.objects.create_user(
            username='settings-staff',
            password='safe-test-password',
        )
        self.organization = Organization.objects.create(
            name='Original Organization Name',
        )

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

    def test_owner_can_update_organization_profile(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('organization_settings'),
            {
                'name': 'Updated Organization Name',
                'address': '12 Business Street',
                'email': 'office@example.com',
                'phone': '9876543210',
                'tax_id': 'BUSINESS-123',
                'invoice_template': (
                    Organization.InvoiceTemplate.CLASSIC
                ),
            },
        )

        self.organization.refresh_from_db()

        self.assertRedirects(
            response,
            reverse('organization_settings'),
        )
        self.assertEqual(
            self.organization.name,
            'Updated Organization Name',
        )
        self.assertEqual(
            self.organization.tax_id,
            'BUSINESS-123',
        )
        self.assertTrue(
            AuditLog.objects.filter(
                organization=self.organization,
                actor=self.owner,
                action=AuditLog.Action.ORGANIZATION_UPDATED,
            ).exists()
        )

    def test_staff_cannot_open_organization_settings(self):
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse('organization_settings'),
        )

        self.assertEqual(response.status_code, 403)

    def test_owner_can_upload_branding_images(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('organization_settings'),
            {
                'name': self.organization.name,
                'address': '',
                'email': '',
                'phone': '',
                'tax_id': '',
                'invoice_template': (
                    Organization.InvoiceTemplate.MODERN
                ),
                'logo': create_test_image('logo.png'),
                'authorized_signature': create_test_image(
                    'signature.png'
                ),
            },
        )

        self.organization.refresh_from_db()

        self.assertRedirects(
            response,
            reverse('organization_settings'),
        )
        self.assertTrue(self.organization.logo.name)
        self.assertTrue(
            self.organization.authorized_signature.name
        )
        self.assertEqual(
            self.organization.invoice_template,
            Organization.InvoiceTemplate.MODERN,
        )

    def test_switches_default_to_off(self):
        self.assertFalse(self.organization.email_invoices_to_customers)
        self.assertFalse(self.organization.send_payment_reminders)

    def test_owner_can_turn_switches_on_and_off(self):
        self.client.force_login(self.owner)
        base = {
            'name': self.organization.name,
            'address': '', 'email': '', 'phone': '', 'tax_id': '',
            'invoice_template': Organization.InvoiceTemplate.CLASSIC,
        }

        self.client.post(
            reverse('organization_settings'),
            {**base, 'email_invoices_to_customers': 'on', 'send_payment_reminders': 'on'},
        )
        self.organization.refresh_from_db()
        self.assertTrue(self.organization.email_invoices_to_customers)
        self.assertTrue(self.organization.send_payment_reminders)

        self.client.post(reverse('organization_settings'), base)
        self.organization.refresh_from_db()
        self.assertFalse(self.organization.email_invoices_to_customers)
        self.assertFalse(self.organization.send_payment_reminders)