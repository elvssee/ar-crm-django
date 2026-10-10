from django import forms

from clients.models import Client

from .models import Project

INPUT_CLASS = (
    "mt-2 block w-full rounded border border-gray-300 bg-white px-3 py-2.5 "
    "text-sm focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
)


class ProjectForm(forms.ModelForm):
    """'firm' is not a field. The client choices are limited to the user's own firm."""

    class Meta:
        model = Project
        fields = [
            "client", "title", "project_type", "site_location",
            "area_sqft", "estimated_fee", "stage", "start_date",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, firm, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.filter(firm=firm)
        self.fields["client"].empty_label = "Select a client"
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS
