from django.urls import path

from . import views

# The team chat is used only from the dashboard's sliding panel; there are no separate discussion pages.
urlpatterns = [
    path("discussions/panel/general/", views.panel_thread, name="panel_general"),
    path("discussions/general/send/", views.discussion_send, name="general_send"),
    path("discussions/general/poll/", views.discussion_poll, name="general_poll"),
    path("discussions/unread/", views.discussion_unread, name="discussion_unread"),
    path("discussions/messages/<int:pk>/file/", views.message_file, name="discussion_file"),
    path("discussions/messages/<int:pk>/delete/", views.discussion_delete, name="discussion_delete"),
]
