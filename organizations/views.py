from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from audit.models import AuditLog
from audit.services import log_action

from .forms import StaffMemberCreateForm, StaffMembershipForm, OrganizationProfileForm
from .models import Membership
from .services import organization_required, role_required

@login_required(login_url='login')
@organization_required
@role_required(Membership.Role.OWNER)
@require_http_methods(['GET', 'POST'])
def organization_settings(request):
    form = OrganizationProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=request.organization,
    )

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            organization = form.save()

            log_action(
                organization=organization,
                actor=request.user,
                action=AuditLog.Action.ORGANIZATION_UPDATED,
                target_type='organization',
                target_id=organization.pk,
                description=(
                    f'Updated organization profile for '
                    f'{organization.name}.'
                ),
            )

        messages.success(
            request,
            'Organization settings updated successfully.',
        )
        return redirect('organization_settings')

    return render(
        request,
        'organizations/organization_settings.html',
        {'form': form},
    )

@login_required(login_url='login')
@organization_required
@role_required(Membership.Role.OWNER)
def staff_list(request):
    staff_memberships = (
        Membership.objects
        .filter(organization=request.organization)
        .exclude(role=Membership.Role.OWNER)
        .select_related('user')
        .order_by('login_username', 'user__username')
    )
    query = request.GET.get('q', '').strip()
    if query:
        staff_memberships = staff_memberships.filter(
            Q(login_username__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__email__icontains=query)
        )
    role = request.GET.get('role', 'all')
    if role in (
        Membership.Role.MANAGER,
        Membership.Role.STAFF,
        Membership.Role.ACCOUNTANT,
    ):
        staff_memberships = staff_memberships.filter(role=role)
    else:
        role = 'all'
    status = request.GET.get('status', 'all')
    if status in ('active', 'inactive'):
        staff_memberships = staff_memberships.filter(is_active=(status == 'active'))
    else:
        status = 'all'
    page_obj = Paginator(staff_memberships, 25).get_page(request.GET.get('page'))

    return render(
        request,
        'organizations/staff_list.html',
        {
            'staff_memberships': page_obj,
            'page_obj': page_obj,
            'query': query,
            'role': role,
            'status': status,
        },
    )


@login_required(login_url='login')
@organization_required
@role_required(Membership.Role.OWNER)
@require_http_methods(['GET', 'POST'])
def staff_create(request):
    form = StaffMemberCreateForm(
        request.POST or None,
        organization=request.organization,
    )

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()

                Membership.objects.create(
                    user=user,
                    organization=request.organization,
                    role=form.cleaned_data['role'],
                    login_username=form.cleaned_data['username'],
                )

                log_action(
                    organization=request.organization,
                    actor=request.user,
                    action=AuditLog.Action.STAFF_CREATED,
                    target_type='membership',
                    target_id=user.pk,
                    description=(
                        f'Created {form.cleaned_data["role"]} account '
                        f'for {form.cleaned_data["username"]}.'
                    ),
                )

        except IntegrityError:
            form.add_error(
                None,
                'This staff account could not be created. Please try again.',
            )
        else:
            messages.success(
                request,
                'Staff account created successfully.',
            )
            return redirect('staff_list')

    return render(
        request,
        'organizations/staff_form.html',
        {
            'form': form,
            'staff_membership': None,
        },
    )


@login_required(login_url='login')
@organization_required
@role_required(Membership.Role.OWNER)
@require_http_methods(['GET', 'POST'])
def staff_update(request, pk):
    staff_membership = get_object_or_404(
        Membership.objects.select_related('user'),
        pk=pk,
        organization=request.organization,
        is_active=True,
    )

    if staff_membership.role == Membership.Role.OWNER:
        return redirect('staff_list')

    form = StaffMembershipForm(
        request.POST or None,
        instance=staff_membership,
    )

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            previous_role = staff_membership.role
            updated_membership = form.save()

            if previous_role != updated_membership.role:
                log_action(
                    organization=request.organization,
                    actor=request.user,
                    action=AuditLog.Action.STAFF_ROLE_CHANGED,
                    target_type='membership',
                    target_id=updated_membership.pk,
                    description=(
                        f'Changed {updated_membership.login_username or updated_membership.user.username} '
                        f'from {previous_role} to '
                        f'{updated_membership.role}.'
                    ),
                )

        messages.success(
            request,
            'Staff role updated successfully.',
        )
        return redirect('staff_list')

    return render(
        request,
        'organizations/staff_form.html',
        {
            'form': form,
            'staff_membership': staff_membership,
        },
    )


@login_required(login_url='login')
@organization_required
@role_required(Membership.Role.OWNER)
@require_POST
def staff_deactivate(request, pk):
    staff_membership = get_object_or_404(
        Membership,
        pk=pk,
        organization=request.organization,
        is_active=True,
    )

    if staff_membership.role == Membership.Role.OWNER:
        messages.error(
            request,
            'Owner access cannot be deactivated from this page.',
        )
        return redirect('staff_list')

    with transaction.atomic():
        staff_membership.is_active = False
        staff_membership.save(update_fields=['is_active'])

        log_action(
            organization=request.organization,
            actor=request.user,
            action=AuditLog.Action.STAFF_DEACTIVATED,
            target_type='membership',
            target_id=staff_membership.pk,
            description=(
                f'Deactivated access for '
                f'{staff_membership.login_username or staff_membership.user.username}.'
            ),
        )

    messages.success(
        request,
        'Staff access has been deactivated.',
    )
    return redirect('staff_list')


@login_required(login_url='login')
@organization_required
@role_required(Membership.Role.OWNER)
@require_POST
def staff_activate(request, pk):
    staff_membership = get_object_or_404(
        Membership,
        pk=pk,
        organization=request.organization,
        is_active=False,
    )

    if staff_membership.role == Membership.Role.OWNER:
        messages.error(request, 'Owner access cannot be activated from this page.')
        return redirect('staff_list')

    with transaction.atomic():
        staff_membership.is_active = True
        staff_membership.save(update_fields=['is_active'])
        log_action(
            organization=request.organization,
            actor=request.user,
            action=AuditLog.Action.STAFF_ACTIVATED,
            target_type='membership',
            target_id=staff_membership.pk,
            description=(
                f'Restored access for '
                f'{staff_membership.login_username or staff_membership.user.username}.'
            ),
        )

    messages.success(request, 'Staff access has been restored.')
    return redirect('staff_list')
