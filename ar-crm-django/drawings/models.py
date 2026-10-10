import os
import uuid

from django.conf import settings
from django.db import models

from .constants import PREVIEW_CONTENT_TYPES


def drawing_upload_path(instance, filename):
    """Random file name on disk: avoids clashes and odd characters. The real name is kept in the database."""
    ext = os.path.splitext(filename)[1].lower()
    return f"firms/{instance.firm_id}/projects/{instance.drawing.project_id}/{uuid.uuid4().hex}{ext}"


class Drawing(models.Model):
    """One drawing (a sheet, model or set) for a project, with one or more files attached."""

    firm = models.ForeignKey("accounts.Firm", on_delete=models.CASCADE, related_name="drawings")
    # PROTECT: a project that still has drawings cannot be deleted by accident.
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, related_name="drawings")
    title = models.CharField(max_length=150)
    revision = models.CharField(max_length=30, blank=True)
    note = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["firm", "-created_at"])]

    def __str__(self):
        return f"{self.title} {self.revision}".strip()


class DrawingFile(models.Model):
    firm = models.ForeignKey("accounts.Firm", on_delete=models.CASCADE, related_name="+")
    drawing = models.ForeignKey(Drawing, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to=drawing_upload_path, max_length=255)
    original_name = models.CharField(max_length=255)
    size = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.original_name

    @property
    def extension(self):
        return os.path.splitext(self.original_name)[1].lower().lstrip(".")

    @property
    def type_label(self):
        return self.extension.upper() or "FILE"

    @property
    def is_previewable(self):
        return self.extension in PREVIEW_CONTENT_TYPES


class ProjectSeen(models.Model):
    """When a user last opened a project's drawings. Used for the 'new' badge."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="+")
    last_seen = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "project"], name="unique_user_project_seen")]
