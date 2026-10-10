from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .models import Firm

User = get_user_model()

INPUT_CLASS = (
    "mt-2 block w-full rounded border border-gray-300 bg-white px-3 py-2.5 "
    "text-sm focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
)


class SignupForm(forms.Form):
    firm_name = forms.CharField(
        label="Firm name", min_length=2, max_length=100,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "Your architecture firm"}),
    )
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "you@firm.com"}),
    )
    password1 = forms.CharField(
        label="Password", strip=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": "At least 8 characters"}),
    )
    password2 = forms.CharField(
        label="Confirm password", strip=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS}),
    )

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "The two passwords do not match.")
            else:
                try:
                    validate_password(p1)
                except forms.ValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned

    @transaction.atomic
    def save(self):
        """Create the firm and its first user (an admin) together, or neither."""
        firm = Firm.objects.create(name=self.cleaned_data["firm_name"].strip())
        return User.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            firm=firm,
            role=User.ROLE_ADMIN,
        )
