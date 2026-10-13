from django import forms

from .models import CatalogItem


class CatalogItemForm(forms.ModelForm):
    class Meta:
        model = CatalogItem
        fields = (
            'item_type',
            'name',
            'cost_price',
            'mrp',
            'default_discount_percent',
            'max_discount_percent',
            'brand',
            'category',
            'origin',
            'stock_quantity',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        self.fields['item_type'].widget.attrs['class'] = 'form-select'
        self.fields['item_type'].help_text = (
            'Products track stock. Services do not use stock.'
        )
        self.fields['cost_price'].required = False
        self.fields['stock_quantity'].required = False
        self.fields['mrp'].required = True
        self.fields['mrp'].label = 'List price (MRP)'
        self.fields['mrp'].help_text = (
            'Invoices start from this price, then apply the selected discount.'
        )
        self.fields['stock_quantity'].help_text = (
            'Available units. Stock is reduced when an invoice is created.'
        )

    def clean(self):
        cleaned_data = super().clean()
        default_discount = cleaned_data.get('default_discount_percent')
        max_discount = cleaned_data.get('max_discount_percent')

        if (
            default_discount is not None
            and max_discount is not None
            and default_discount > max_discount
        ):
            self.add_error(
                'default_discount_percent',
                'Default discount cannot be higher than the maximum discount.',
            )

        if cleaned_data.get('item_type') == CatalogItem.ItemType.SERVICE:
            cleaned_data['stock_quantity'] = 0
        elif cleaned_data.get('stock_quantity') is None:
            cleaned_data['stock_quantity'] = 0

        if cleaned_data.get('cost_price') is None:
            cleaned_data['cost_price'] = 0

        return cleaned_data
