from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .models import Membership


def get_active_membership(request):
    if not request.user.is_authenticated:
        return None

    memberships = Membership.objects.select_related('organization').filter(
        user=request.user,
        is_active=True,
        organization__is_active=True,
    )

    active_organization_id = request.session.get(
        'active_organization_id'
    )

    if active_organization_id:
        membership = memberships.filter(
            organization_id=active_organization_id
        ).first()

        if membership:
            return membership

    membership = memberships.first()

    if membership:
        request.session['active_organization_id'] = (
            membership.organization_id
        )

    return membership

def user_has_membership(user):
    return user.organization_memberships.exists()

def organization_required(view_func):
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        membership = get_active_membership(request)

        if membership is None:
            if user_has_membership(request.user):
                return redirect('membership_inactive')

            return redirect('organization_setup')

        request.membership = membership
        request.organization = membership.organization

        return view_func(request, *args, **kwargs)

    return wrapped_view

def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            membership = getattr(request, 'membership', None)

            if membership is None:
                return HttpResponseForbidden(
                    'You do not have access to an active organization.'
                )

            if membership.role not in allowed_roles:
                return HttpResponseForbidden(
                    'You do not have permission to perform this action.'
                )

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator