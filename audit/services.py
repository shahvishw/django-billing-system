from .models import AuditLog


def log_action(
    *,
    organization,
    actor,
    action,
    target_type,
    target_id,
    description='',
):
    if not getattr(actor, 'is_authenticated', False):
        actor = None

    return AuditLog.objects.create(
        organization=organization,
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        description=description,
    )