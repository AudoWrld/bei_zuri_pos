from django.contrib.auth.forms import UserCreationForm, UserChangeForm, SetPasswordForm
from django import forms
from users.models import User


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    phone_number = forms.CharField(required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = [
            choice for choice in User.ROLE_CHOICES
            if choice[0] != User.CUSTOMER
        ]

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "role",
            "is_staff",
            "is_active",
        )


class CustomUserChangeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        if self.instance and self.current_user and self.instance == self.current_user:
            self.fields['is_staff'].disabled = True
            self.fields['is_active'].disabled = True
            self.fields['is_superuser'].disabled = True
        self.fields['role'].choices = [
            choice for choice in User.ROLE_CHOICES
            if choice[0] != User.CUSTOMER
        ]

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "role",
            "is_staff",
            "is_active",
            "is_superuser",
        )
