from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from organizations.models import Membership, Organization
from organizations.services import get_active_membership,user_has_membership

from .forms import OrganizationSetupForm, OwnerRegistrationForm
from .throttling import (
    clear_login_failures,
    is_login_blocked,
    login_throttle_keys,
    record_login_failure,
)


def login_view(request):
    form_context = {
        'next_url': request.POST.get('next') or request.GET.get('next', ''),
        'username': request.POST.get('username', ''),
        'organization': request.POST.get('organization', ''),
    }

    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        throttle_keys = login_throttle_keys(
            username,
            request.META.get(settings.LOGIN_RATE_LIMIT_IP_HEADER, ''),
        )

        if is_login_blocked(throttle_keys):
            response = render(
                request,
                'accounts/login.html',
                {
                    **form_context,
                    'error': 'Too many sign-in attempts. Please wait 15 minutes and try again.',
                },
                status=429,
            )
            response['Retry-After'] = '900'
            return response

        user = authenticate(
            request,
            username=username,
            password=password,
            organization_name=request.POST.get('organization', '').strip(),
        )

        if user:
            clear_login_failures(throttle_keys)
            login(request, user)
            next_url = form_context['next_url']
            selected_membership = getattr(
                request,
                'organization_login_membership',
                None,
            )
            if selected_membership is not None:
                request.session['active_organization_id'] = (
                    selected_membership.organization_id
                )

            if get_active_membership(request) is not None:
                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)
                return redirect('dashboard')

            if user_has_membership(user):
                return redirect('membership_inactive')

            return redirect('organization_setup')

        record_login_failure(throttle_keys)

        context = {**form_context, 'error': 'Invalid credentials'}
        if getattr(request, 'organization_login_ambiguous', False):
            context['error'] = (
                'These credentials match accounts in more than one organization. '
                'Enter your organization name or ID below to choose the right account.'
            )

        return render(request, 'accounts/login.html', context)

    return render(request, 'accounts/login.html', form_context)

def register_owner(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = OwnerRegistrationForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()

                organization = Organization.objects.create(
                    name=form.cleaned_data['organization_name'].strip(),
                )

                Membership.objects.create(
                    user=user,
                    organization=organization,
                    role=Membership.Role.OWNER,
                    login_username=user.username,
                )

        except IntegrityError:
            form.add_error(
                None,
                'Your account could not be created. Please try again.',
            )
        else:
            login(request, user)

            request.session['active_organization_id'] = (
                organization.pk
            )

            return redirect('dashboard')

    return render(
        request,
        'accounts/register.html',
        {'form': form},
    )

@login_required(login_url='login')
def organization_setup(request):
    if get_active_membership(request) is not None:
        return redirect('dashboard')

    if user_has_membership(request.user):
        return redirect('membership_inactive')

    form = OrganizationSetupForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                organization = Organization.objects.create(
                    name=form.cleaned_data['organization_name'].strip(),
                )

                Membership.objects.create(
                    user=request.user,
                    organization=organization,
                    role=Membership.Role.OWNER,
                    login_username=request.user.username,
                )

        except IntegrityError:
            form.add_error(
                None,
                'Your organization could not be created. Please try again.',
            )
        else:
            request.session['active_organization_id'] = (
                organization.pk
            )

            return redirect('dashboard')

    return render(
        request,
        'accounts/organization_setup.html',
        {'form': form},
    )

@login_required(login_url='login')
def membership_inactive(request):
    if get_active_membership(request) is not None:
        return redirect('dashboard')

    if not user_has_membership(request.user):
        return redirect('organization_setup')

    return render(
        request,
        'accounts/membership_inactive.html',
    )

@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')
