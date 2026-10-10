from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from clients.models import Client
from clients.views import firm_clients, firm_required
from projects.views import firm_projects

from .forms import ActivityForm, FollowUpForm
from .models import Activity, FollowUp


def firm_activities(request):
    return Activity.objects.filter(firm=request.user.firm)


def firm_followups(request):
    return FollowUp.objects.filter(firm=request.user.firm)


def safe_next(request, default_name):
    """Where to go after saving. Only ever stays on this site."""
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return reverse(default_name)


def can_modify_activity(user, activity):
    return user.is_firm_admin or activity.created_by_id == user.id


def can_modify_followup(user, followup):
    return user.is_firm_admin or user.id in (followup.created_by_id, followup.assigned_to_id)


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- activity log

@firm_required
def activity_list(request):
    activities = firm_activities(request).select_related("client", "project", "created_by")
    client_id = to_int(request.GET.get("client"))
    kind = request.GET.get("kind", "")
    if client_id:
        activities = activities.filter(client_id=client_id)
    if kind in dict(Activity.KIND_CHOICES):
        activities = activities.filter(kind=kind)
    else:
        kind = ""
    page = Paginator(activities, 50).get_page(request.GET.get("page"))
    for activity in page:
        activity.can_modify = can_modify_activity(request.user, activity)
    params = request.GET.copy()
    params.pop("page", None)
    context = {
        "page": page,
        "clients": firm_clients(request),
        "kinds": Activity.KIND_CHOICES,
        "client_id": client_id,
        "kind": kind,
        "querystring": params.urlencode(),
    }
    return render(request, "activities/activity_list.html", context)


@firm_required
def activity_create(request):
    initial = {}
    project_id = to_int(request.GET.get("project"))
    client_id = to_int(request.GET.get("client"))
    if project_id:
        project = firm_projects(request).filter(pk=project_id).first()
        if project:
            initial.update(project=project.pk, client=project.client_id)
    elif client_id and firm_clients(request).filter(pk=client_id).exists():
        initial["client"] = client_id
    form = ActivityForm(request.POST or None, firm=request.user.firm, initial=initial)
    if request.method == "POST" and form.is_valid():
        activity = form.save(commit=False)
        activity.firm = request.user.firm
        activity.created_by = request.user
        activity.save()
        messages.success(request, "Activity logged.")
        return redirect(safe_next(request, "activity_list"))
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    return render(request, "activities/activity_form.html", {"form": form, "title": "Log activity", "next": next_url})


@firm_required
def activity_edit(request, pk):
    activity = get_object_or_404(firm_activities(request), pk=pk)
    if not can_modify_activity(request.user, activity):
        return HttpResponseForbidden("Only an admin or the person who logged this can change it.")
    form = ActivityForm(request.POST or None, instance=activity, firm=request.user.firm)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Activity updated.")
        return redirect(safe_next(request, "activity_list"))
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    return render(request, "activities/activity_form.html", {"form": form, "title": "Edit activity", "next": next_url})


@firm_required
def activity_delete(request, pk):
    activity = get_object_or_404(firm_activities(request), pk=pk)
    if not can_modify_activity(request.user, activity):
        return HttpResponseForbidden("Only an admin or the person who logged this can delete it.")
    if request.method == "POST":
        activity.delete()
        messages.success(request, "Activity deleted.")
        return redirect(safe_next(request, "activity_list"))
    next_url = request.GET.get("next", "")
    return render(request, "activities/activity_confirm_delete.html", {"activity": activity, "next": next_url})


@firm_required
def project_activity(request, project_pk):
    """Everything about one project in one place: its activity history and its follow-ups."""
    project = get_object_or_404(firm_projects(request), pk=project_pk)
    activities = list(
        firm_activities(request).filter(project=project).select_related("client", "created_by")
    )
    for activity in activities:
        activity.can_modify = can_modify_activity(request.user, activity)
    followups = list(
        firm_followups(request).filter(project=project).select_related("assigned_to")
    )
    for followup in followups:
        followup.can_modify = can_modify_followup(request.user, followup)
    return render(
        request,
        "activities/project_activity.html",
        {"project": project, "activities": activities, "followups": followups,
         "here": reverse("project_activity", args=[project.pk])},
    )


# ------------------------------------------------------------------ follow-ups

@firm_required
def followup_list(request):
    scope = request.GET.get("scope", "all")
    status = request.GET.get("status", "open")
    followups = firm_followups(request).select_related("project", "project__client", "assigned_to")
    if scope == "mine":
        followups = followups.filter(assigned_to=request.user)
    else:
        scope = "all"
    today = timezone.localdate()
    if status == "done":
        items = list(followups.filter(done=True).order_by("-done_at")[:100])
        groups = [("Completed", items)]
    else:
        status = "open"
        items = list(followups.filter(done=False).order_by("due_date", "id"))
        groups = [
            ("Overdue", [f for f in items if f.due_date < today]),
            ("Due today", [f for f in items if f.due_date == today]),
            ("Upcoming", [f for f in items if f.due_date > today]),
        ]
    for followup in items:
        followup.can_modify = can_modify_followup(request.user, followup)
    return render(
        request,
        "activities/followup_list.html",
        {"groups": groups, "scope": scope, "status": status, "total": len(items),
         "here": request.get_full_path()},
    )


@firm_required
def followup_create(request):
    initial = {"assigned_to": request.user.pk}
    project_id = to_int(request.GET.get("project"))
    if project_id and firm_projects(request).filter(pk=project_id).exists():
        initial["project"] = project_id
    form = FollowUpForm(request.POST or None, firm=request.user.firm, initial=initial)
    if request.method == "POST" and form.is_valid():
        followup = form.save(commit=False)
        followup.firm = request.user.firm
        followup.created_by = request.user
        followup.save()
        messages.success(request, "Follow-up added.")
        return redirect(safe_next(request, "followup_list"))
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    return render(request, "activities/followup_form.html", {"form": form, "title": "Add follow-up", "next": next_url})


@firm_required
def followup_edit(request, pk):
    followup = get_object_or_404(firm_followups(request), pk=pk)
    if not can_modify_followup(request.user, followup):
        return HttpResponseForbidden("Only an admin, or the person who created or was assigned this, can change it.")
    form = FollowUpForm(request.POST or None, instance=followup, firm=request.user.firm)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Follow-up updated.")
        return redirect(safe_next(request, "followup_list"))
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    return render(request, "activities/followup_form.html", {"form": form, "title": "Edit follow-up", "next": next_url})


@firm_required
@require_POST
def followup_toggle(request, pk):
    followup = get_object_or_404(firm_followups(request), pk=pk)
    if not can_modify_followup(request.user, followup):
        return HttpResponseForbidden("You can't change this follow-up.")
    followup.done = not followup.done
    followup.done_at = timezone.now() if followup.done else None
    followup.save(update_fields=["done", "done_at"])
    return redirect(safe_next(request, "followup_list"))


@firm_required
@require_POST
def followup_delete(request, pk):
    followup = get_object_or_404(firm_followups(request), pk=pk)
    if not can_modify_followup(request.user, followup):
        return HttpResponseForbidden("You can't delete this follow-up.")
    followup.delete()
    messages.success(request, "Follow-up deleted.")
    return redirect(safe_next(request, "followup_list"))
