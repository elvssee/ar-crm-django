from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from clients.views import firm_clients, firm_required

from .forms import ProjectForm
from .models import Project


def firm_projects(request):
    """The ONLY way views get projects: always limited to the user's own firm."""
    return Project.objects.filter(firm=request.user.firm).select_related("client")


@firm_required
def project_list(request):
    projects = firm_projects(request)
    stage = request.GET.get("stage", "")
    q = request.GET.get("q", "").strip()
    if stage in dict(Project.STAGE_CHOICES):
        projects = projects.filter(stage=stage)
    else:
        stage = ""
    if q:
        projects = projects.filter(Q(title__icontains=q) | Q(client__name__icontains=q))
    context = {
        "projects": projects,
        "q": q,
        "stage": stage,
        "stages": Project.STAGE_CHOICES,
    }
    return render(request, "projects/project_list.html", context)


@firm_required
def project_board(request):
    """Kanban board: one column per stage, built from the firm's own projects only."""
    projects = list(firm_projects(request).order_by("-updated_at"))
    values = [value for value, _ in Project.STAGE_CHOICES]
    columns = []
    for index, (value, label) in enumerate(Project.STAGE_CHOICES):
        items = [p for p in projects if p.stage == value]
        for p in items:
            p.prev_stage = values[index - 1] if index > 0 else None
            p.next_stage = values[index + 1] if index < len(values) - 1 else None
        columns.append(
            {
                "value": value,
                "label": label,
                "projects": items,
                "count": len(items),
                "total": sum((p.estimated_fee or 0) for p in items),
            }
        )
    open_value = sum(c["total"] for c in columns if c["value"] != Project.STAGE_COMPLETED)
    return render(
        request,
        "projects/project_board.html",
        {"columns": columns, "open_value": open_value, "total_projects": len(projects)},
    )


@firm_required
@require_POST
def project_move(request, pk):
    project = get_object_or_404(firm_projects(request), pk=pk)
    stage = request.POST.get("stage", "")
    if stage not in dict(Project.STAGE_CHOICES):
        return HttpResponseBadRequest("Unknown stage")
    project.stage = stage
    project.save(update_fields=["stage", "updated_at"])
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "stage": stage})
    return redirect("project_board")


@firm_required
def project_create(request):
    if not firm_clients(request).exists():
        messages.info(request, "Add a client first, then you can create a project for them.")
        return redirect("client_create")
    form = ProjectForm(request.POST or None, firm=request.user.firm)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.firm = request.user.firm
        project.save()
        messages.success(request, f"{project.title} was added.")
        return redirect("project_list")
    return render(request, "projects/project_form.html", {"form": form, "title": "Add project"})


@firm_required
def project_edit(request, pk):
    project = get_object_or_404(firm_projects(request), pk=pk)
    form = ProjectForm(request.POST or None, instance=project, firm=request.user.firm)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{project.title} was updated.")
        return redirect("project_list")
    return render(
        request, "projects/project_form.html", {"form": form, "title": f"Edit {project.title}"}
    )


@firm_required
def project_delete(request, pk):
    project = get_object_or_404(firm_projects(request), pk=pk)
    if request.method == "POST":
        title = project.title
        project.delete()
        messages.success(request, f"{title} was deleted.")
        return redirect("project_list")
    return render(request, "projects/project_confirm_delete.html", {"project": project})
