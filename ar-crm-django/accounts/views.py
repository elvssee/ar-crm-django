from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .dashboard import build_dashboard
from .forms import SignupForm


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("dashboard")
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def dashboard(request):
    # True only for the first dashboard shown after signing in (staged fade-in).
    post_login = bool(request.session.pop("just_logged_in", False))
    if request.user.firm_id is None:
        return render(request, "accounts/dashboard.html", {"firm": None, "post_login": post_login})
    context = build_dashboard(request.user)
    context["post_login"] = post_login
    return render(request, "accounts/dashboard.html", context)
