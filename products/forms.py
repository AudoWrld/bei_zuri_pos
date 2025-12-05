from django import forms
from django.core.validators import MinValueValidator
from django_select2.forms import Select2Widget
from .models import Product, Category, Brand, Barcode


class ProductForm(forms.ModelForm):
    name = forms.CharField(required=True)
    sku = forms.CharField(required=False)
    barcodes = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text="Scan or enter barcodes"
    )
    cost_price = forms.DecimalField(required=True, validators=[MinValueValidator(0.01)])
    selling_price = forms.DecimalField(
        required=True, validators=[MinValueValidator(0.01)]
    )
    wholesale_price = forms.DecimalField(
        required=True, validators=[MinValueValidator(0.01)]
    )
    special_price = forms.DecimalField(
        required=True, validators=[MinValueValidator(0.01)]
    )
    quantity = forms.IntegerField(required=True, validators=[MinValueValidator(1)])

    class Meta:
        model = Product
        fields = [
            "name",
            "description",
            "category",
            "brand",
            "sku",
            "cost_price",
            "special_price",
            "wholesale_price",
            "selling_price",
            "quantity",
            "low_stock_threshold",
            "weight",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "category": Select2Widget(attrs={"data-placeholder": "Search for a category..."}),
            "brand": Select2Widget(attrs={"data-placeholder": "Search for a brand..."}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ["name", "description"]