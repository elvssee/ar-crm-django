from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def remember_fresh_login(sender, request, user, **kwargs):
    """Flag a fresh sign-in so the dashboard can fade its content in once."""
    if request is not None and hasattr(request, "session"):
        request.session["just_logged_in"] = True
