from django.contrib import admin

from .models import Activity, FollowUp


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("summary", "kind", "client", "project", "occurred_on", "created_by")
    list_filter = ("firm", "kind")
    search_fields = ("summary", "client__name")


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ("note", "project", "due_date", "assigned_to", "done")
    list_filter = ("firm", "done")
    search_fields = ("note", "project__title")
