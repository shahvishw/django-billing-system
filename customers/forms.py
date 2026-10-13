import re

from django import forms
from django.core.exceptions import ValidationError

from .models import Customer

PHONE_ERROR = (
    'Enter a valid phone number: 10 digits, or start with + and the '
    'country code for a number outside India.'
)


def normalize_phone(raw):
    """Return one standard form of a phone number, or raise ValidationError.

    Indian numbers are stored as 10 digits ("+91", "91" and a leading "0"
    are removed). Other countries must start with "+" and are stored as
    "+" followed by digits.
    """
    value = (raw or '').strip()

    if not value or re.search(r'[^\d\s\-().+]', value):
        raise ValidationError(PHONE_ERROR)

    has_plus = value.startswith('+')
    digits = re.sub(r'\D', '', value)

    if value.count('+') > (1 if has_plus else 0):
        raise ValidationError(PHONE_ERROR)

    if len(digits) == 12 and digits.startswith('91'):
        return digits[2:]

    if has_plus:
        if 8 <= len(digits) <= 15:
            return '+' + digits
        raise ValidationError(PHONE_ERROR)

    if len(digits) == 11 and digits.startswith('0'):
        return digits[1:]

    if len(digits) == 10:
        return digits

    raise ValidationError(PHONE_ERROR)


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'email', 'phone', 'address']

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data['phone'])

        existing = Customer.objects.filter(
            organization=self.organization,
            phone=phone,
        ).exclude(pk=self.instance.pk).first()

        if existing:
            raise forms.ValidationError(
                f'A customer with this phone number already exists '
                f'in your business ({existing.name}).'
            )

        return phone

    def clean_email(self):
        email = self.cleaned_data['email']

        if not email:
            return ''

        duplicates = Customer.objects.filter(
            organization=self.organization,
            email__iexact=email,
        ).exclude(pk=self.instance.pk)

        if duplicates.exists():
            raise forms.ValidationError(
                'A customer with this email already exists in your business.'
            )

        return email