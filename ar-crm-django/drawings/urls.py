from django.urls import path

from . import views

urlpatterns = [
    path("drawings/", views.drawing_feed, name="drawing_feed"),
    path("projects/<int:project_pk>/drawings/", views.project_drawings, name="project_drawings"),
    path("projects/<int:project_pk>/drawings/upload/", views.drawing_upload, name="drawing_upload"),
    path("drawings/<int:pk>/edit/", views.drawing_edit, name="drawing_edit"),
    path("drawings/<int:pk>/delete/", views.drawing_delete, name="drawing_delete"),
    path("drawings/files/<int:pk>/", views.drawing_file, name="drawing_file"),
]
