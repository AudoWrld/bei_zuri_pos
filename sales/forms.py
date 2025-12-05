from django import forms
from django.forms import formset_factory, modelformset_factory
from .models import Sale, ReturnItem


class ReturnStartForm(forms.Form):
    sale_number = forms.CharField(
        max_length=20,
        label="Sale Number",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter sale number (e.g., SALE-20241125-0001)",
                "autofocus": True,
            }
        ),
    )

    def clean_sale_number(self):
        sale_number = self.cleaned_data["sale_number"].upper()
        try:
            sale = Sale.objects.get(sale_number=sale_number)
            if not sale.completed_at:
                raise forms.ValidationError("This sale has not been completed yet.")
            return sale_number
        except Sale.DoesNotExist:
            raise forms.ValidationError("Sale with this number does not exist.")


class ReturnItemForm(forms.Form):
    sale_item_id = forms.IntegerField(widget=forms.HiddenInput())
    quantity = forms.IntegerField(
        min_value=0, widget=forms.NumberInput(attrs={"class": "qty-input", "min": "0"})
    )
    return_reason = forms.ChoiceField(
        choices=ReturnItem.RETURN_REASONS,
        widget=forms.Select(
            attrs={
                "class": "form-control",
                "style": "width: 100px; padding: 8px 10px; text-align: center; border: 2px solid #e0e0e0; border-radius: 4px; font-weight: 600; color: #00bcd4; font-size: 15px;",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        self.sale_item = kwargs.pop("sale_item", None)
        super().__init__(*args, **kwargs)
        if self.sale_item:
            self.fields["quantity"].max_value = self.sale_item.quantity
            self.fields["quantity"].widget.attrs["max"] = str(self.sale_item.quantity)
            self.fields["sale_item_id"].initial = self.sale_item.id

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if self.sale_item and quantity > self.sale_item.quantity:
            raise forms.ValidationError(
                f"Cannot return more than {self.sale_item.quantity} units."
            )
        return quantity


def get_return_formset(sale_items):
    """Create a formset class for return items"""
    ReturnFormSet = formset_factory(ReturnItemForm, extra=0)

    initial_data = []
    for item in sale_items:
        initial_data.append(
            {"sale_item_id": item.id, "quantity": 0, "return_reason": "FAULTY"}
        )

    class CustomReturnFormSet(ReturnFormSet):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, initial=initial_data, **kwargs)
            for form, item in zip(self, sale_items):
                form.sale_item = item

    return CustomReturnFormSet
