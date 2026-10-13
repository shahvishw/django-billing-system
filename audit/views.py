from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils.dateparse import parse_date

from organizations.models import Membership
from organizations.services import organization_required, role_required

from .models import AuditLog


@login_required(login_url='login')
@organization_required
@role_required(Membership.Role.OWNER)
def audit_log_list(request):
    audit_logs = AuditLog.objects.filter(
        organization=request.organization,
    ).select_related('actor')
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    parsed_from = parse_date(date_from) if date_from else None
    parsed_to = parse_date(date_to) if date_to else None
    if parsed_from:
        audit_logs = audit_logs.filter(created_at__date__gte=parsed_from)
    else:
        date_from = ''
    if parsed_to:
        audit_logs = audit_logs.filter(created_at__date__lte=parsed_to)
    else:
        date_to = ''
    page_obj = Paginator(audit_logs, 50).get_page(request.GET.get('page'))
    actor_ids = [log.actor_id for log in page_obj if log.actor_id]
    actor_names = dict(
        Membership.objects.filter(
            organization=request.organization,
            user_id__in=actor_ids,
        ).values_list('user_id', 'login_username')
    )
    for log in page_obj:
        log.actor_display = (
            actor_names.get(log.actor_id)
            or (log.actor.username if log.actor else 'System')
        )

    return render(
        request,
        'audit/audit_log_list.html',
        {
            'audit_logs': page_obj,
            'page_obj': page_obj,
            'date_from': date_from,
            'date_to': date_to,
        },
    )
