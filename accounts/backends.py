from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from organizations.models import Membership


class OrganizationUsernameBackend(ModelBackend):
    """Authenticate staff by their username within an organization."""

    def authenticate(
        self,
        request,
        username=None,
        password=None,
        organization_name='',
        **kwargs,
    ):
        if not username or password is None:
            return None

        if request is not None:
            request.organization_login_ambiguous = False
            request.organization_login_choices = []

        username = username.strip()
        memberships = Membership.objects.select_related(
            'user', 'organization'
        ).filter(
            Q(login_username__iexact=username)
            | Q(login_username='', user__username__iexact=username)
        )

        if organization_name:
            organization_name = organization_name.strip()
            organization_filter = Q(organization__name__iexact=organization_name)
            if organization_name.isdecimal():
                organization_filter |= Q(organization_id=int(organization_name))
            memberships = memberships.filter(organization_filter)

        candidates = list(memberships)
        if candidates:
            matching_memberships = [
                membership
                for membership in candidates
                if self.user_can_authenticate(membership.user)
                and membership.user.check_password(password)
            ]
            matching_users = {
                membership.user_id: membership.user
                for membership in matching_memberships
            }

            # A shared username and password must never select another person's account.
            if len(matching_users) > 1:
                if request is not None:
                    request.organization_login_ambiguous = True
                return None

            if not matching_users:
                return None

            user = next(iter(matching_users.values()))
            if request is not None:
                request.organization_login_membership = matching_memberships[0]
            return user

        if organization_name:
            return None

        user = super().authenticate(
            request,
            username=username,
            password=password,
            **kwargs,
        )
        if user and user.organization_memberships.exists():
            return None
        return user
