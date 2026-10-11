import os

from django import forms

from drawings.constants import ALLOWED_EXTENSIONS
from drawings.forms import max_upload_mb

INPUT_CLASS = (
    "block w-full rounded border border-gray-300 bg-white px-3 py-2.5 "
    "text-sm focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
)


class MessageForm(forms.Form):
    body = forms.CharField(
        max_length=2000, required=False,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 2, "placeholder": "Write a message…"}),
    )
    attachment = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            "class": "hidden", "data-attach-input": "",
            "accept": ",".join("." + ext for ext in sorted(ALLOWED_EXTENSIONS)),
        }),
    )

    def clean_body(self):
        return self.cleaned_data["body"].strip()

    def clean_attachment(self):
        upload = self.cleaned_data.get("attachment")
        if not upload:
            return None
        extension = os.path.splitext(upload.name)[1].lower().lstrip(".")
        if extension not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                f"“{upload.name}” is not an allowed file type. Allowed: " + ", ".join(sorted(ALLOWED_EXTENSIONS)) + "."
            )
        if upload.size > max_upload_mb() * 1024 * 1024:
            raise forms.ValidationError(f"“{upload.name}” is larger than {max_upload_mb()} MB.")
        return upload

    def clean(self):
        cleaned = super().clean()
        # A message needs words, a file, or both. (Field errors are reported on their own.)
        if not self.errors and not cleaned.get("body") and not cleaned.get("attachment"):
            raise forms.ValidationError("Write a message or attach a file.")
        return cleaned
