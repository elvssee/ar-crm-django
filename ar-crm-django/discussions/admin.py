from django.contrib import admin

from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("short_body", "project", "firm", "author", "created_at")
    list_filter = ("firm",)
    search_fields = ("body", "project__title")

    @admin.display(description="Message")
    def short_body(self, obj):
        return obj.body[:60]
