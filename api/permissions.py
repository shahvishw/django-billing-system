from rest_framework.permissions import BasePermission

from organizations.services import get_active_membership


class ActiveOrganizationPermission(BasePermission):
    """Require an active membership and enforce a view's allowed roles."""

    message = 'You do not have access to this organization resource.'

    def has_permission(self, request, view):
        membership = get_active_membership(request)
        if membership is None:
            return False

        request.membership = membership
        request.organization = membership.organization
        allowed_roles = getattr(view, 'allowed_roles', None)
        return allowed_roles is None or membership.role in allowed_roles
