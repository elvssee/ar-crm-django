from django.contrib import admin

from .models import Drawing, DrawingFile


class DrawingFileInline(admin.TabularInline):
    model = DrawingFile
    extra = 0
    readonly_fields = ("original_name", "size", "created_at")


@admin.register(Drawing)
class DrawingAdmin(admin.ModelAdmin):
    list_display = ("title", "revision", "project", "firm", "uploaded_by", "created_at")
    list_filter = ("firm",)
    search_fields = ("title", "project__title")
    inlines = [DrawingFileInline]
