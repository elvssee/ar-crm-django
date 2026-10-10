from django.conf import settings
from django.db import models
from django.utils import timezone


class Activity(models.Model):
    """A call, meeting, site visit, email or note about a client (and optionally one of their projects)."""

    KIND_CHOICES = [
        ("call", "Call"),
        ("meeting", "Meeting"),
        ("site_visit", "Site visit"),
        ("email", "Email"),
        ("note", "Note"),
    ]

    firm = models.ForeignKey("accounts.Firm", on_delete=models.CASCADE, related_name="+")
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="activities")
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="activities"
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="note")
    summary = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    occurred_on = models.DateField(default=timezone.localdate)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurred_on", "-id"]
        indexes = [models.Index(fields=["firm", "-occurred_on"])]
        verbose_name_plural = "activities"

    def __str__(self):
        return self.summary


class FollowUp(models.Model):
    """Something to do by a due date, tied to a project and assigned to a person."""

    firm = models.ForeignKey("accounts.Firm", on_delete=models.CASCADE, related_name="+")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="followups")
    note = models.CharField(max_length=255)
    due_date = models.DateField()
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["done", "due_date", "id"]
        indexes = [models.Index(fields=["firm", "done", "due_date"])]

    def __str__(self):
        return self.note

    @property
    def is_overdue(self):
        return not self.done and self.due_date < timezone.localdate()

    @property
    def is_due_today(self):
        return not self.done and self.due_date == timezone.localdate()
