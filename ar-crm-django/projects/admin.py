from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "firm", "client", "project_type", "stage")
    list_filter = ("firm", "stage", "project_type")
    search_fields = ("title", "client__name")
