from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from organizations.models import Membership, Organization

from .models import AuditLog
from .services import log_action


User = get_user_model()


class AuditLogTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='audit-owner',
            password='safe-test-password',
        )
        self.other_owner = User.objects.create_user(
            username='other-audit-owner',
            password='safe-test-password',
        )

        self.organization = Organization.objects.create(
            name='Audit Organization',
        )
        self.other_organization = Organization.objects.create(
            name='Other Audit Organization',
        )

        Membership.objects.create(
            user=self.owner,
            organization=self.organization,
            role=Membership.Role.OWNER,
        )
        Membership.objects.create(
            user=self.other_owner,
            organization=self.other_organization,
            role=Membership.Role.OWNER,
        )

    def test_log_action_creates_a_tenant_scoped_record(self):
        log = log_action(
            organization=self.organization,
            actor=self.owner,
            action=AuditLog.Action.STAFF_CREATED,
            target_type='membership',
            target_id='42',
            description='Created staff account for sales-user.',
        )

        self.assertEqual(log.organization, self.organization)
        self.assertEqual(log.actor, self.owner)
        self.assertEqual(
            log.action,
            AuditLog.Action.STAFF_CREATED,
        )

    def test_owner_only_sees_their_organization_logs(self):
        log_action(
            organization=self.organization,
            actor=self.owner,
            action=AuditLog.Action.STAFF_CREATED,
            target_type='membership',
            target_id='42',
            description='Visible organization activity.',
        )
        log_action(
            organization=self.other_organization,
            actor=self.other_owner,
            action=AuditLog.Action.STAFF_CREATED,
            target_type='membership',
            target_id='99',
            description='Private organization activity.',
        )

        self.client.force_login(self.owner)

        response = self.client.get(reverse('audit_log_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Visible organization activity.',
        )
        self.assertNotContains(
            response,
            'Private organization activity.',
        )