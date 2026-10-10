import os

from django import forms
from django.conf import settings

from .constants import ALLOWED_EXTENSIONS, DEFAULT_MAX_UPLOAD_MB
from .models import Drawing

INPUT_CLASS = (
    "mt-2 block w-full rounded border border-gray-300 bg-white px-3 py-2.5 "
    "text-sm focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(item, initial) for item in data]
        return [single_file_clean(data, initial)]


def max_upload_mb():
    return getattr(settings, "DRAWING_MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB)


class DrawingUploadForm(forms.Form):
    title = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "e.g. Ground floor plan"}),
    )
    revision = forms.CharField(
        max_length=30, required=False,
        widget=forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "e.g. Rev B"}),
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3, "placeholder": "e.g. Ready for client review"}),
    )
    files = MultipleFileField(
        label="Files",
        widget=MultipleFileInput(attrs={"class": INPUT_CLASS, "multiple": True}),
    )

    def clean_files(self):
        files = self.cleaned_data["files"]
        limit_bytes = max_upload_mb() * 1024 * 1024
        for uploaded in files:
            extension = os.path.splitext(uploaded.name)[1].lower().lstrip(".")
            if extension not in ALLOWED_EXTENSIONS:
                raise forms.ValidationError(
                    f"“{uploaded.name}” is not an allowed file type. "
                    "Allowed: " + ", ".join(sorted(ALLOWED_EXTENSIONS)) + "."
                )
            if uploaded.size > limit_bytes:
                raise forms.ValidationError(
                    f"“{uploaded.name}” is larger than {max_upload_mb()} MB."
                )
        return files


class DrawingEditForm(forms.ModelForm):
    class Meta:
        model = Drawing
        fields = ["title", "revision", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS
