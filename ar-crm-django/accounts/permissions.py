from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden


def admin_required(view):
    """Login required, and the user must be an admin of a firm."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if user.firm_id is None or not user.is_firm_admin:
            return HttpResponseForbidden("Only firm admins can do this.")
        return view(request, *args, **kwargs)

    return wrapper
