from django.urls import path

from . import views

urlpatterns = [
    path("activities/", views.activity_list, name="activity_list"),
    path("activities/new/", views.activity_create, name="activity_create"),
    path("activities/<int:pk>/edit/", views.activity_edit, name="activity_edit"),
    path("activities/<int:pk>/delete/", views.activity_delete, name="activity_delete"),
    path("projects/<int:project_pk>/activity/", views.project_activity, name="project_activity"),
    path("projects/<int:project_pk>/activity/new/", views.project_activity_create, name="project_activity_create"),
    path("projects/<int:project_pk>/followups/", views.project_followups, name="project_followups"),
    path("projects/<int:project_pk>/followups/new/", views.project_followup_create, name="project_followup_create"),
    path("followups/", views.followup_list, name="followup_list"),  # all projects; opened from the dashboard
    path("followups/<int:pk>/edit/", views.followup_edit, name="followup_edit"),
    path("followups/<int:pk>/done/", views.followup_toggle, name="followup_toggle"),
    path("followups/<int:pk>/delete/", views.followup_delete, name="followup_delete"),
]
