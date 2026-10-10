from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ClientForm
from .models import Client


def firm_required(view):
    """Login required, and the user must belong to a firm."""

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.firm_id is None:
            return HttpResponseForbidden("Your account is not linked to a firm.")
        return view(request, *args, **kwargs)

    return wrapper


def firm_clients(request):
    """The ONLY way views get clients: always limited to the user's own firm."""
    return Client.objects.filter(firm=request.user.firm)


@firm_required
def client_list(request):
    clients = firm_clients(request)
    q = request.GET.get("q", "").strip()
    if q:
        clients = clients.filter(
            Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q)
        )
    return render(request, "clients/client_list.html", {"clients": clients, "q": q})


@firm_required
def client_create(request):
    form = ClientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        client = form.save(commit=False)
        client.firm = request.user.firm
        client.save()
        messages.success(request, f"{client.name} was added.")
        return redirect("client_list")
    return render(request, "clients/client_form.html", {"form": form, "title": "Add client"})


@firm_required
def client_edit(request, pk):
    client = get_object_or_404(firm_clients(request), pk=pk)
    form = ClientForm(request.POST or None, instance=client)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{client.name} was updated.")
        return redirect("client_list")
    return render(
        request, "clients/client_form.html", {"form": form, "title": f"Edit {client.name}"}
    )


@firm_required
def client_delete(request, pk):
    client = get_object_or_404(firm_clients(request), pk=pk)
    if request.method == "POST":
        name = client.name
        client.delete()
        messages.success(request, f"{name} was deleted.")
        return redirect("client_list")
    return render(request, "clients/client_confirm_delete.html", {"client": client})
