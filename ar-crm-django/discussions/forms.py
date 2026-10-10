from django import forms

from drawings.models import Drawing

INPUT_CLASS = (
    "block w-full rounded border border-gray-300 bg-white px-3 py-2.5 "
    "text-sm focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-700/20"
)


class MessageForm(forms.Form):
    body = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 2, "placeholder": "Write a message…"}),
    )
    drawing = forms.ModelChoiceField(
        queryset=Drawing.objects.none(), required=False, empty_label="Attach a drawing (optional)",
        widget=forms.Select(attrs={"class": INPUT_CLASS}),
    )

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        # Only drawings of THIS project (and therefore this firm) can be attached.
        self.fields["drawing"].queryset = Drawing.objects.filter(firm=project.firm, project=project)

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if not body:
            raise forms.ValidationError("Write something first.")
        return body
