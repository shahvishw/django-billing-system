import hashlib
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import LoginThrottle


WINDOW = timedelta(minutes=15)
LOCKOUT = timedelta(minutes=15)
USERNAME_LIMIT = 5
IP_LIMIT = 20


def _key(kind, value):
    normalized = (value or '').strip().casefold() if kind == 'username' else (value or '').strip()
    return hashlib.sha256(f'{kind}:{normalized}'.encode('utf-8')).hexdigest()


def login_throttle_keys(username, remote_addr):
    return (
        (_key('username', username), USERNAME_LIMIT),
        (_key('ip', remote_addr), IP_LIMIT),
    )


def is_login_blocked(keys):
    now = timezone.now()
    LoginThrottle.objects.filter(updated_at__lt=now - WINDOW).delete()
    return LoginThrottle.objects.filter(
        key__in=[key for key, _limit in keys],
        blocked_until__gt=now,
    ).exists()


def record_login_failure(keys):
    now = timezone.now()
    for key, limit in keys:
        with transaction.atomic():
            throttle, created = LoginThrottle.objects.select_for_update().get_or_create(
                key=key,
                defaults={'failures': 1, 'window_started_at': now},
            )
            if created:
                continue

            if now - throttle.window_started_at >= WINDOW:
                throttle.failures = 0
                throttle.window_started_at = now
                throttle.blocked_until = None

            throttle.failures += 1
            if throttle.failures >= limit:
                throttle.blocked_until = now + LOCKOUT

            throttle.save(
                update_fields=[
                    'failures',
                    'window_started_at',
                    'blocked_until',
                    'updated_at',
                ]
            )


def clear_login_failures(keys):
    LoginThrottle.objects.filter(
        key__in=[key for key, _limit in keys],
    ).delete()
