from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("clients/", include("clients.urls")),
    path("projects/", include("projects.urls")),
    path("", include("accounts.urls")),
]
