import uuid

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import Membership,Organization


User = get_user_model()


STAFF_ROLE_CHOICES = (
    (Membership.Role.MANAGER, 'Manager'),
    (Membership.Role.STAFF, 'Staff'),
    (Membership.Role.ACCOUNTANT, 'Accountant'),
)


class StaffMemberCreateForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(
        choices=STAFF_ROLE_CHOICES,
    )

    class Meta:
        model = User
        fields = (
            'username',
            'email',
            'password1',
            'password2',
        )

    def __init__(self, *args, organization=None, **kwargs):
        self.organization = organization
        self.internal_username = None
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'

        self.fields['username'].label = 'Username'
        self.fields['username'].help_text = (
            'This username only needs to be unique within this organization.'
        )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'An account already exists with this email address.'
            )

        return email

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if self.organization and Membership.objects.filter(
            organization=self.organization,
            login_username__iexact=username,
        ).exists():
            raise ValidationError(
                'This username is already used in this organization.'
            )

        if User.objects.filter(username__iexact=username).exists():
            self.internal_username = f'staff-{uuid.uuid4().hex}'
        else:
            self.internal_username = username
        return username

    def _post_clean(self):
        submitted_username = self.cleaned_data.get('username')
        if submitted_username and self.internal_username:
            self.cleaned_data['username'] = self.internal_username
        super()._post_clean()
        if submitted_username:
            self.cleaned_data['username'] = submitted_username


class StaffMembershipForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ('role',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['role'].choices = STAFF_ROLE_CHOICES
        self.fields['role'].widget.attrs['class'] = 'form-select'

class OrganizationProfileForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = (
            'name',
            'address',
            'email',
            'phone',
            'tax_id',
            'logo',
            'authorized_signature',
            'invoice_template',
            'discount_mode',
            'tax_rate_percent',
            'email_invoices_to_customers',
            'send_payment_reminders',
        )
        widgets = {
            'address': forms.Textarea(
                attrs={
                    'rows': 4,
                }
            ),
            'invoice_template': forms.RadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.is_bound and (
            'discount_mode' not in self.data
            or 'tax_rate_percent' not in self.data
        ):
            self.data = self.data.copy()
            if 'discount_mode' not in self.data:
                self.data['discount_mode'] = self.instance.discount_mode
            if 'tax_rate_percent' not in self.data:
                self.data['tax_rate_percent'] = self.instance.tax_rate_percent

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        self.fields['invoice_template'].widget.attrs.pop(
            'class',
            None,
        )

    def clean_logo(self):
        logo = self.cleaned_data.get('logo')

        if logo and logo.size > 2 * 1024 * 1024:
            raise forms.ValidationError(
                'Logo image must be 2 MB or smaller.'
            )

        return logo

    def clean_authorized_signature(self):
        signature = self.cleaned_data.get(
            'authorized_signature'
        )

        if signature and signature.size > 2 * 1024 * 1024:
            raise forms.ValidationError(
                'Signature image must be 2 MB or smaller.'
            )

        return signature
