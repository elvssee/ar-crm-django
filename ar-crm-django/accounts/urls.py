from django.contrib.auth import views as auth_views
from django.urls import path

from . import team_views, views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("signup/", views.signup, name="signup"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("account/password/", team_views.AccountPasswordChangeView.as_view(), name="password_change"),
    path("team/", team_views.team_list, name="team_list"),
    path("team/invite/", team_views.invite_create, name="invite_create"),
    path("team/invite/<int:pk>/revoke/", team_views.invite_revoke, name="invite_revoke"),
    path("team/<int:pk>/active/", team_views.member_set_active, name="member_set_active"),
    path("team/<int:pk>/role/", team_views.member_set_role, name="member_set_role"),
    path("join/<str:token>/", team_views.accept_invite, name="accept_invite"),
]
