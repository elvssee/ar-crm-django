from .services import unread_counts


def unread_total(request):
    """Makes {{ unread_total }} available in every template, for the menu badge."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or user.firm_id is None:
        return {}
    return {"unread_total": sum(unread_counts(user).values())}
