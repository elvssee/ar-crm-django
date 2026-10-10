from django.contrib import messages as flash
from django.db.models import Count, Max
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from clients.views import firm_required
from projects.views import firm_projects

from .forms import MessageForm
from .models import Message
from .services import last_seen_for, mark_seen, unread_counts


def is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def firm_messages(request):
    """The ONLY way views get messages: always limited to the user's own firm."""
    return Message.objects.filter(firm=request.user.firm)


def decorate(messages, user, last_seen=None):
    for message in messages:
        message.is_mine = message.author_id == user.id
        message.can_delete = user.is_firm_admin or message.is_mine
        message.is_new = bool(last_seen) and not message.is_mine and message.created_at > last_seen
    return messages


@firm_required
def discussion_inbox(request):
    projects = list(
        firm_projects(request)
        .annotate(last_message_at=Max("chat_messages__created_at"), message_count=Count("chat_messages"))
        .filter(message_count__gt=0)
        .order_by("-last_message_at")
    )
    unread = unread_counts(request.user)
    latest = {}
    for message in firm_messages(request).select_related("author").order_by("-id")[:500]:
        latest.setdefault(message.project_id, message)
    for project in projects:
        project.unread = unread.get(project.pk, 0)
        project.latest = latest.get(project.pk)
    return render(request, "discussions/inbox.html", {"projects": projects})


@firm_required
def project_discussion(request, project_pk):
    project = get_object_or_404(firm_projects(request), pk=project_pk)
    last_seen = last_seen_for(request.user, project)
    recent = list(
        firm_messages(request).filter(project=project).select_related("author", "drawing").order_by("-id")[:200]
    )
    recent.reverse()
    decorate(recent, request.user, last_seen)
    mark_seen(request.user, project)  # after computing which messages were new
    form = MessageForm(project=project)
    return render(
        request, "discussions/thread.html", {"project": project, "messages_list": recent, "form": form}
    )


@firm_required
@require_POST
def discussion_send(request, project_pk):
    project = get_object_or_404(firm_projects(request), pk=project_pk)
    form = MessageForm(request.POST, project=project)
    if not form.is_valid():
        error = " ".join(e for errors in form.errors.values() for e in errors)
        if is_ajax(request):
            return HttpResponseBadRequest(error)
        flash.error(request, error)
        return redirect("project_discussion", project_pk=project.pk)
    message = Message.objects.create(
        firm=request.user.firm,
        project=project,
        author=request.user,
        body=form.cleaned_data["body"],
        drawing=form.cleaned_data["drawing"],
    )
    mark_seen(request.user, project)
    if is_ajax(request):
        decorate([message], request.user)
        return render(request, "discussions/_message.html", {"message": message}, status=201)
    return redirect("project_discussion", project_pk=project.pk)


@firm_required
@require_GET
def discussion_poll(request, project_pk):
    """Called every few seconds by the page: returns only messages newer than ?after=<id>."""
    project = get_object_or_404(firm_projects(request), pk=project_pk)
    try:
        after = int(request.GET.get("after", "0"))
    except ValueError:
        after = 0
    new_messages = list(
        firm_messages(request)
        .filter(project=project, id__gt=after)
        .select_related("author", "drawing")
        .order_by("id")
    )
    if not new_messages:
        return HttpResponse("")
    decorate(new_messages, request.user)
    mark_seen(request.user, project)
    return render(request, "discussions/_message_list.html", {"messages_list": new_messages})


@firm_required
@require_POST
def discussion_delete(request, pk):
    message = get_object_or_404(firm_messages(request), pk=pk)
    if not (request.user.is_firm_admin or message.author_id == request.user.id):
        return HttpResponseForbidden("You can only delete your own messages.")
    project_pk = message.project_id
    message.delete()
    return redirect("project_discussion", project_pk=project_pk)
