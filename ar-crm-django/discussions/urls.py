from django.urls import path

from . import views

urlpatterns = [
    path("discussions/", views.discussion_inbox, name="discussion_inbox"),
    path("projects/<int:project_pk>/discussion/", views.project_discussion, name="project_discussion"),
    path("projects/<int:project_pk>/discussion/send/", views.discussion_send, name="discussion_send"),
    path("projects/<int:project_pk>/discussion/poll/", views.discussion_poll, name="discussion_poll"),
    path("discussions/messages/<int:pk>/delete/", views.discussion_delete, name="discussion_delete"),
]
