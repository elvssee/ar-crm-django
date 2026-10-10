from django.contrib import messages
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from clients.views import firm_required
from projects.views import firm_projects

from .constants import PREVIEW_CONTENT_TYPES
from .forms import DrawingEditForm, DrawingUploadForm, max_upload_mb
from .models import Drawing, DrawingFile, ProjectSeen


def firm_drawings(request):
    """The ONLY way views get drawings: always limited to the user's own firm."""
    return Drawing.objects.filter(firm=request.user.firm)


def can_modify(user, drawing):
    return user.is_firm_admin or drawing.uploaded_by_id == user.id


def annotate(drawings, user):
    """Mark which drawings are new to this user, and which they may edit or delete."""
    seen = {s.project_id: s.last_seen for s in ProjectSeen.objects.filter(user=user)}
    baseline = user.date_joined
    for drawing in drawings:
        last_seen = max(seen.get(drawing.project_id, baseline), baseline)
        drawing.is_new = drawing.uploaded_by_id != user.id and drawing.created_at > last_seen
        drawing.can_modify = can_modify(user, drawing)
    return drawings


@firm_required
def drawing_feed(request):
    drawings = list(
        firm_drawings(request)
        .select_related("project", "project__client", "uploaded_by")
        .prefetch_related("files")[:100]
    )
    annotate(drawings, request.user)
    new_count = sum(1 for d in drawings if d.is_new)
    return render(request, "drawings/feed.html", {"drawings": drawings, "new_count": new_count})


@firm_required
def project_drawings(request, project_pk):
    project = get_object_or_404(firm_projects(request), pk=project_pk)
    drawings = list(
        firm_drawings(request)
        .filter(project=project)
        .select_related("uploaded_by")
        .prefetch_related("files")
    )
    annotate(drawings, request.user)  # compute 'new' first, then mark as seen
    ProjectSeen.objects.update_or_create(
        user=request.user, project=project, defaults={"last_seen": timezone.now()}
    )
    return render(request, "drawings/project_drawings.html", {"project": project, "drawings": drawings})


@firm_required
def drawing_upload(request, project_pk):
    project = get_object_or_404(firm_projects(request), pk=project_pk)
    form = DrawingUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            drawing = Drawing.objects.create(
                firm=request.user.firm,
                project=project,
                title=form.cleaned_data["title"].strip(),
                revision=form.cleaned_data["revision"].strip(),
                note=form.cleaned_data["note"].strip(),
                uploaded_by=request.user,
            )
            for uploaded in form.cleaned_data["files"]:
                DrawingFile.objects.create(
                    firm=request.user.firm,
                    drawing=drawing,
                    file=uploaded,
                    original_name=uploaded.name[:255],
                    size=uploaded.size,
                )
        count = len(form.cleaned_data["files"])
        messages.success(request, f"{drawing.title} was uploaded ({count} file{'s' if count != 1 else ''}).")
        return redirect("project_drawings", project_pk=project.pk)
    return render(
        request,
        "drawings/upload_form.html",
        {"form": form, "project": project, "max_mb": max_upload_mb()},
    )


@firm_required
def drawing_file(request, pk):
    """Serves a file only to logged-in people from the same firm."""
    drawing_file = get_object_or_404(DrawingFile, pk=pk, firm=request.user.firm)
    extension = drawing_file.extension
    inline = extension in PREVIEW_CONTENT_TYPES and request.GET.get("download") != "1"
    try:
        handle = drawing_file.file.open("rb")
    except (FileNotFoundError, ValueError):
        raise Http404("File not found")
    return FileResponse(
        handle,
        as_attachment=not inline,
        filename=drawing_file.original_name,
        content_type=PREVIEW_CONTENT_TYPES.get(extension, "application/octet-stream") if inline else "application/octet-stream",
    )


@firm_required
def drawing_edit(request, pk):
    drawing = get_object_or_404(firm_drawings(request), pk=pk)
    if not can_modify(request.user, drawing):
        return HttpResponseForbidden("Only an admin or the person who uploaded this can change it.")
    form = DrawingEditForm(request.POST or None, instance=drawing)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{drawing.title} was updated.")
        return redirect("project_drawings", project_pk=drawing.project_id)
    return render(request, "drawings/drawing_form.html", {"form": form, "drawing": drawing})


@firm_required
def drawing_delete(request, pk):
    drawing = get_object_or_404(firm_drawings(request), pk=pk)
    if not can_modify(request.user, drawing):
        return HttpResponseForbidden("Only an admin or the person who uploaded this can delete it.")
    if request.method == "POST":
        project_pk = drawing.project_id
        title = drawing.title
        drawing.delete()
        messages.success(request, f"{title} was deleted.")
        return redirect("project_drawings", project_pk=project_pk)
    return render(request, "drawings/drawing_confirm_delete.html", {"drawing": drawing})
