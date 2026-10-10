from django import forms

from .models import Client

INPUT_CLASS = (
    "mt-2 block w-full rounded border border-gray-300 bg-white px-3 py-2.5 "
    "text-sm focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
)


class ClientForm(forms.ModelForm):
    """Note: 'firm' is deliberately not a field. The view sets it from the logged-in user."""

    class Meta:
        model = Client
        fields = ["name", "phone", "email", "address", "source", "notes"]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS
