"""Helpers used only by the invoice PDF templates."""
from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def fit_image(image_field, box):
    """Return width/height attributes that fit an image inside a box (in pt).

    Usage:  <img src="{{ org.logo.url }}" {{ org.logo|fit_image:"150,56" }}>
    The aspect ratio is kept and scaled to the largest size that fits.
    xhtml2pdf ignores max-width/max-height, so the size has to be explicit.
    """
    try:
        max_w, max_h = (float(part) for part in str(box).split(','))
    except ValueError:
        max_w, max_h = 150.0, 56.0

    try:
        width, height = float(image_field.width), float(image_field.height)
        scale = min(max_w / width, max_h / height)
        width, height = width * scale, height * scale
    except Exception:
        width, height = max_w, max_h

    return format_html('width="{}" height="{}"', round(width), round(height))


@register.filter
def status_label(invoice):
    return {
        'paid': 'PAID',
        'partially_paid': 'PARTIALLY PAID',
        'overdue': 'OVERDUE',
    }.get(invoice.payment_status, 'UNPAID')
