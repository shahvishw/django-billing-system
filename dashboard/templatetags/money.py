"""Money formatting filters (Indian digit grouping: 1,13,988.00)."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()


def _group_indian(integer_part):
    if len(integer_part) <= 3:
        return integer_part
    head, tail = integer_part[:-3], integer_part[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ','.join(parts + [tail])


def _format(value, decimals=2):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    quantum = Decimal(1).scaleb(-decimals)
    amount = amount.quantize(quantum, rounding=ROUND_HALF_UP)
    sign = '-' if amount < 0 else ''
    whole, _, fraction = f'{abs(amount):f}'.partition('.')
    text = _group_indian(whole)
    return f'{sign}{text}.{fraction}' if decimals else f'{sign}{text}'


@register.filter
def inr(value):
    """{{ 113988|inr }} -> ₹1,13,988.00  (empty values render as a dash)."""
    if value in (None, ''):
        return '—'
    text = _format(value)
    if text is None:
        return value
    return f'-₹{text[1:]}' if text.startswith('-') else f'₹{text}'


@register.filter
def inr_plain(value):
    """Same grouping without the rupee sign: 1,13,988.00"""
    if value in (None, ''):
        return '—'
    text = _format(value)
    return value if text is None else text
