from django import forms
from django.contrib.auth import get_user_model

from clients.models import Client
from projects.models import Project

from .models import Activity, FollowUp

User = get_user_model()

INPUT_CLASS = (
    "mt-2 block w-full rounded border border-gray-300 bg-white px-3 py-2.5 "
    "text-sm focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
)


def style_fields(form):
    for field in form.fields.values():
        field.widget.attrs["class"] = INPUT_CLASS


class ActivityForm(forms.ModelForm):
    """'firm' is not a field. Clients and projects are limited to the user's own firm."""

    class Meta:
        model = Activity
        fields = ["client", "project", "kind", "summary", "details", "occurred_on"]
        widgets = {
            "details": forms.Textarea(attrs={"rows": 4}),
            "occurred_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, firm, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.filter(firm=firm)
        self.fields["client"].empty_label = "Select a client"
        self.fields["project"].queryset = Project.objects.filter(firm=firm).select_related("client")
        self.fields["project"].empty_label = "No specific project"
        style_fields(self)

    def clean(self):
        cleaned = super().clean()
        client, project = cleaned.get("client"), cleaned.get("project")
        if client and project and project.client_id != client.pk:
            self.add_error("project", "That project belongs to a different client.")
        return cleaned


class ProjectActivityForm(forms.ModelForm):
    """Logging an activity from a project's own page: the project (and its client) are fixed by the view."""

    class Meta:
        model = Activity
        fields = ["kind", "summary", "details", "occurred_on"]
        widgets = {
            "details": forms.Textarea(attrs={"rows": 4}),
            "occurred_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_fields(self)


class FollowUpForm(forms.ModelForm):
    """The project is never a field: it comes from the project page the person is on."""

    class Meta:
        model = FollowUp
        fields = ["note", "due_date", "assigned_to"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, firm, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(firm=firm, is_active=True)
        self.fields["assigned_to"].empty_label = "Select a person"
        self.fields["assigned_to"].required = True
        self.fields["assigned_to"].label_from_instance = lambda user: user.display_name
        style_fields(self)
