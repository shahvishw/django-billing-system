from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


User = get_user_model()


class OwnerRegistrationForm(UserCreationForm):
    organization_name = forms.CharField(
        max_length=150,
        label='Business name',
    )
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = (
            'username',
            'email',
            'password1',
            'password2',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        self.fields['organization_name'].widget.attrs[
            'placeholder'
        ] = 'Enter your business name'

        self.fields['username'].widget.attrs[
            'placeholder'
        ] = 'Choose a username'

        self.fields['email'].widget.attrs[
            'placeholder'
        ] = 'Enter your email address'

    def clean_email(self):
        email = self.cleaned_data['email'].lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                'An account already exists with this email address.'
            )

        return email

class OrganizationSetupForm(forms.Form):
    organization_name = forms.CharField(
        max_length=150,
        label='Business name',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['organization_name'].widget.attrs.update(
            {
                'class': 'form-control',
                'placeholder': 'Enter your business name',
            }
        )