from django.contrib import messages as flash
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from clients.views import firm_required
from drawings.constants import PREVIEW_CONTENT_TYPES

from .forms import MessageForm
from .models import Message
from .services import last_seen_for, mark_seen, unread_counts

# Discussions live only in the sliding panel on the dashboard, and they are one firm-wide team chat.
# Every message here has project=None. (Older project threads stay in the database but are never shown.)


def is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def firm_messages(request):
    """The ONLY way views get messages: always limited to the user's own firm."""
    return Message.objects.filter(firm=request.user.firm)


def team_messages(request):
    return firm_messages(request).filter(project__isnull=True)


def decorate(messages, user, last_seen=None):
    for message in messages:
        message.is_mine = message.author_id == user.id
        message.can_delete = user.is_firm_admin or message.is_mine
        message.is_new = bool(last_seen) and not message.is_mine and message.created_at > last_seen
    return messages


def load_thread(request):
    last_seen = last_seen_for(request.user, None)
    recent = list(team_messages(request).select_related("author").order_by("-id")[:200])
    recent.reverse()
    decorate(recent, request.user, last_seen)
    mark_seen(request.user, None)  # after computing which messages were new
    return {
        "room": {
            "title": "Team chat",
            "subtitle": "Everyone in your firm",
            "send_url": reverse("general_send"),
            "poll_url": reverse("general_poll"),
        },
        "messages_list": recent,
        "form": MessageForm(),
    }


@firm_required
@require_POST
def discussion_send(request):
    form = MessageForm(request.POST, request.FILES)
    if not form.is_valid():
        error = " ".join(e for errors in form.errors.values() for e in errors)
        if is_ajax(request):
            return HttpResponseBadRequest(error)
        flash.error(request, error)
        return redirect("dashboard")
    upload = form.cleaned_data.get("attachment")
    message = Message.objects.create(
        firm=request.user.firm,
        project=None,
        author=request.user,
        body=form.cleaned_data["body"],
        attachment=upload or "",
        attachment_name=upload.name[:255] if upload else "",
        attachment_size=upload.size if upload else 0,
    )
    mark_seen(request.user, None)
    if is_ajax(request):
        decorate([message], request.user)
        return render(request, "discussions/_message.html", {"message": message}, status=201)
    return redirect("dashboard")


@firm_required
@require_GET
def discussion_poll(request):
    """Called every few seconds by the panel: returns only messages newer than ?after=<id>."""
    try:
        after = int(request.GET.get("after", "0"))
    except ValueError:
        after = 0
    new_messages = list(
        team_messages(request).filter(id__gt=after).select_related("author").order_by("id")
    )
    if not new_messages:
        return HttpResponse("")
    decorate(new_messages, request.user)
    mark_seen(request.user, None)
    return render(request, "discussions/_message_list.html", {"messages_list": new_messages})


@firm_required
@require_POST
def discussion_delete(request, pk):
    message = get_object_or_404(team_messages(request), pk=pk)
    if not (request.user.is_firm_admin or message.author_id == request.user.id):
        return HttpResponseForbidden("You can only delete your own messages.")
    if message.attachment:
        message.attachment.delete(save=False)  # do not leave the file behind on disk
    message.delete()
    if is_ajax(request):
        return JsonResponse({"ok": True})
    return redirect("dashboard")


@firm_required
@require_GET
def message_file(request, pk):
    """Serves a chat file only to logged-in people from the same firm."""
    message = get_object_or_404(team_messages(request), pk=pk)
    if not message.attachment:
        raise Http404("No file")
    extension = message.extension
    inline = extension in PREVIEW_CONTENT_TYPES and request.GET.get("download") != "1"
    try:
        handle = message.attachment.open("rb")
    except (FileNotFoundError, ValueError):
        raise Http404("File not found")
    return FileResponse(
        handle,
        as_attachment=not inline,
        filename=message.attachment_name,
        content_type=PREVIEW_CONTENT_TYPES.get(extension, "application/octet-stream") if inline else "application/octet-stream",
    )


# ---- the sliding panel on the dashboard: returns a small HTML piece, not a whole page

@firm_required
@require_GET
def panel_thread(request):
    return render(request, "discussions/_panel_thread.html", load_thread(request))


@firm_required
@require_GET
def discussion_unread(request):
    return JsonResponse({"total": sum(unread_counts(request.user).values())})
