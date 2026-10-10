from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "firm", "phone", "email", "source", "created_at")
    list_filter = ("firm", "source")
    search_fields = ("name", "email", "phone")
