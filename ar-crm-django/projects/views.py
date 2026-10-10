from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

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
