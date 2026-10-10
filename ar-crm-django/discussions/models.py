from django.conf import settings
from django.db import models


class Message(models.Model):
    """One chat message in a project's discussion thread."""

    firm = models.ForeignKey("accounts.Firm", on_delete=models.CASCADE, related_name="+")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="chat_messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    body = models.TextField(max_length=2000)
    # Optional: point at a drawing of the same project, so a question stays tied to the right sheet.
    drawing = models.ForeignKey(
        "drawings.Drawing", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["project", "id"])]

    def __str__(self):
        return self.body[:50]


class ChatSeen(models.Model):
    """When a user last read a project's thread. Drives the unread counts."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="+")
    last_seen = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "project"], name="unique_user_project_chatseen")]
