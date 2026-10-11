import os
import uuid

from django.conf import settings
from django.db import models

from drawings.constants import PREVIEW_CONTENT_TYPES


def chat_upload_path(instance, filename):
    """Random file name on disk, kept inside the firm's own folder. The real name lives in the database."""
    ext = os.path.splitext(filename)[1].lower()
    return f"firms/{instance.firm_id}/chat/{uuid.uuid4().hex}{ext}"


class Message(models.Model):
    """One chat message. In a project's thread, or (project empty) in the firm-wide team chat."""

    firm = models.ForeignKey("accounts.Firm", on_delete=models.CASCADE, related_name="+")
    # Empty project = the general team chat that belongs to the whole firm.
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="chat_messages", null=True, blank=True
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    body = models.TextField(max_length=2000)
    # Optional: point at a drawing of the same project, so a question stays tied to the right sheet.
    drawing = models.ForeignKey(
        "drawings.Drawing", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # Optional file sent in the chat (a plan, a photo, a document...).
    attachment = models.FileField(upload_to=chat_upload_path, max_length=255, blank=True)
    attachment_name = models.CharField(max_length=255, blank=True)
    attachment_size = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["project", "id"])]

    def __str__(self):
        return self.body[:50] or self.attachment_name

    @property
    def extension(self):
        return os.path.splitext(self.attachment_name)[1].lower().lstrip(".")

    @property
    def type_label(self):
        return self.extension.upper() or "FILE"

    @property
    def is_previewable(self):
        return self.extension in PREVIEW_CONTENT_TYPES


class ChatSeen(models.Model):
    """When a user last read a thread (project empty = the team chat). Drives the unread counts."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="+", null=True, blank=True
    )
    last_seen = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "project"], name="unique_user_project_chatseen"),
            models.UniqueConstraint(
                fields=["user"], condition=models.Q(project__isnull=True), name="unique_user_general_chatseen"
            ),
        ]
