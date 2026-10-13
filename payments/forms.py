from django import forms

from .models import Payment


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            'amount',
            'method',
            'received_on',
            'reference',
            'notes',
        ]
        widgets = {
            'amount': forms.NumberInput(
                attrs={
                    'class': 'payment-input',
                    'step': '0.01',
                    'min': '0.01',
                }
            ),
            'received_on': forms.DateInput(
                attrs={
                    'class': 'payment-input',
                    'type': 'date',
                }
            ),
            'reference': forms.TextInput(
                attrs={
                    'class': 'payment-input',
                    'placeholder': 'Optional payment reference',
                }
            ),
            'notes': forms.Textarea(
                attrs={
                    'class': 'payment-input',
                    'rows': 3,
                    'placeholder': 'Optional internal notes',
                }
            ),
        }

    def __init__(self, *args, invoice, **kwargs):
        super().__init__(*args, **kwargs)
        self.invoice = invoice

        self.fields['amount'].label = 'Amount received'
        self.fields['received_on'].label = 'Received on'

    def clean_amount(self):
        amount = self.cleaned_data['amount']

        if amount > self.invoice.balance_due:
            raise forms.ValidationError(
                f'Amount cannot exceed the remaining balance of '
                f'₹{self.invoice.balance_due}.'
            )

        return amount