from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from activities.models import FollowUp

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
    context = {"firm": request.user.firm}
    if request.user.firm_id:
        today = timezone.localdate()
        context["due_followups"] = list(
            FollowUp.objects.filter(
                firm=request.user.firm, assigned_to=request.user, done=False, due_date__lte=today
            )
            .select_related("project")
            .order_by("due_date", "id")[:8]
        )
    return render(request, "accounts/dashboard.html", context)
