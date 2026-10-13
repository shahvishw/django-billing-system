from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from organizations.models import Membership, Organization


User = get_user_model()


class OwnerRegistrationTests(TestCase):
    def registration_data(self):
        return {
            'organization_name': 'North Star Traders',
            'username': 'northstar-owner',
            'email': 'owner@northstar.example',
            'password1': 'StrongPassword123!',
            'password2': 'StrongPassword123!',
        }

    def test_registration_page_is_public(self):
        response = self.client.get(reverse('register'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Create your business account',
        )

    def test_registration_creates_owner_and_organization(self):
        response = self.client.post(
            reverse('register'),
            data=self.registration_data(),
        )

        user = User.objects.get(username='northstar-owner')
        organization = Organization.objects.get(
            name='North Star Traders',
        )
        membership = Membership.objects.get(
            user=user,
            organization=organization,
        )

        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(
            membership.role,
            Membership.Role.OWNER,
        )
        self.assertEqual(
            self.client.session['active_organization_id'],
            organization.pk,
        )

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(
            username='existing-user',
            email='owner@northstar.example',
            password='safe-test-password',
        )

        response = self.client.post(
            reverse('register'),
            data=self.registration_data(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'An account already exists with this email address.',
        )
        self.assertEqual(Organization.objects.count(), 0)

    def test_failed_membership_creation_rolls_back_registration(self):
        with patch(
            'accounts.views.Membership.objects.create',
            side_effect=IntegrityError,
        ):
            response = self.client.post(
                reverse('register'),
                data=self.registration_data(),
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Your account could not be created. Please try again.',
        )
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Organization.objects.count(), 0)

    def test_login_redirects_user_without_membership_to_setup(self):
        user = User.objects.create_user(
            username='no-membership-user',
            password='safe-test-password',
        )

        response = self.client.post(
            reverse('login'),
            data={
                'username': user.username,
                'password': 'safe-test-password',
            },
        )

        self.assertRedirects(
            response,
            reverse('organization_setup'),
        )

    def test_dashboard_redirects_user_without_membership_to_setup(self):
        user = User.objects.create_user(
            username='dashboard-no-membership',
            password='safe-test-password',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertRedirects(
            response,
            reverse('organization_setup'),
        )

class OrganizationSetupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='existing-user',
            password='safe-test-password',
        )
        self.client.force_login(self.user)

    def test_setup_page_is_available_to_user_without_membership(self):
        response = self.client.get(
            reverse('organization_setup'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Set up your business')

    def test_setup_creates_owner_membership(self):
        response = self.client.post(
            reverse('organization_setup'),
            data={
                'organization_name': 'Existing User Business',
            },
        )

        organization = Organization.objects.get(
            name='Existing User Business',
        )
        membership = Membership.objects.get(
            user=self.user,
            organization=organization,
        )

        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(
            membership.role,
            Membership.Role.OWNER,
        )
        self.assertEqual(
            self.client.session['active_organization_id'],
            organization.pk,
        )

    def test_user_with_membership_cannot_reopen_setup(self):
        organization = Organization.objects.create(
            name='Existing Organization',
        )
        Membership.objects.create(
            user=self.user,
            organization=organization,
            role=Membership.Role.OWNER,
        )

        response = self.client.get(
            reverse('organization_setup'),
        )

        self.assertRedirects(response, reverse('dashboard'))