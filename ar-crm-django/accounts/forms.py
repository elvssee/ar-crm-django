from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone

from .models import Firm, Invitation

User = get_user_model()

INPUT_CLASS = (
    "mt-2 block w-full rounded border border-gray-300 bg-white px-3 py-2.5 "
    "text-sm focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
)


class InvitationUnavailable(Exception):
    """The invitation was used or expired while the form was being submitted."""


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


class InviteForm(forms.Form):
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "junior@firm.com"}),
    )
    role = forms.ChoiceField(
        label="Role", choices=User.ROLE_CHOICES, initial=User.ROLE_MEMBER,
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )

    def __init__(self, *args, firm, **kwargs):
        super().__init__(*args, **kwargs)
        self.firm = firm

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Someone with this email already has an account.")
        already_invited = Invitation.objects.filter(
            firm=self.firm, email__iexact=email,
            accepted_at__isnull=True, expires_at__gt=timezone.now(),
        ).exists()
        if already_invited:
            raise forms.ValidationError(
                "This email already has a pending invitation. Revoke it first to send a new one."
            )
        return email


class AcceptInviteForm(forms.Form):
    first_name = forms.CharField(
        label="First name", max_length=150,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    last_name = forms.CharField(
        label="Last name", max_length=150, required=False,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    password1 = forms.CharField(
        label="Password", strip=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS, "placeholder": "At least 8 characters"}),
    )
    password2 = forms.CharField(
        label="Confirm password", strip=False,
        widget=forms.PasswordInput(attrs={"class": INPUT_CLASS}),
    )

    def __init__(self, *args, invitation, **kwargs):
        super().__init__(*args, **kwargs)
        self.invitation = invitation

    def clean(self):
        cleaned = super().clean()
        if User.objects.filter(email__iexact=self.invitation.email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "The two passwords do not match.")
            else:
                candidate = User(
                    email=self.invitation.email, first_name=cleaned.get("first_name", "")
                )
                try:
                    validate_password(p1, user=candidate)
                except forms.ValidationError as exc:
                    self.add_error("password1", exc)
        return cleaned

    @transaction.atomic
    def save(self):
        invitation = Invitation.objects.select_for_update().get(pk=self.invitation.pk)
        if not invitation.is_pending:
            raise InvitationUnavailable()
        user = User.objects.create_user(
            email=invitation.email,
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data.get("last_name", "").strip(),
            firm=invitation.firm,
            role=invitation.role,
        )
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["accepted_at"])
        return user


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS
