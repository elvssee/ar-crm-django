from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import AcceptInviteForm, InvitationUnavailable, InviteForm, StyledPasswordChangeForm
from .models import Invitation
from .permissions import admin_required

User = get_user_model()


@admin_required
def team_list(request):
    firm = request.user.firm
    members = User.objects.filter(firm=firm).order_by("role", "email")
    invitations = list(
        Invitation.objects.filter(
            firm=firm, accepted_at__isnull=True, expires_at__gt=timezone.now()
        )
    )
    for invitation in invitations:
        invitation.url = request.build_absolute_uri(
            reverse("accept_invite", args=[invitation.token])
        )
    return render(
        request,
        "accounts/team_list.html",
        {"members": members, "invitations": invitations, "roles": User.ROLE_CHOICES},
    )


@admin_required
def invite_create(request):
    form = InviteForm(request.POST or None, firm=request.user.firm)
    if request.method == "POST" and form.is_valid():
        invitation = Invitation.objects.create(
            firm=request.user.firm,
            email=form.cleaned_data["email"],
            role=form.cleaned_data["role"],
            invited_by=request.user,
        )
        messages.success(
            request,
            f"Invitation created for {invitation.email}. Copy the link below and send it to them.",
        )
        return redirect("team_list")
    return render(request, "accounts/invite_form.html", {"form": form})


@admin_required
@require_POST
def invite_revoke(request, pk):
    invitation = get_object_or_404(
        Invitation, pk=pk, firm=request.user.firm, accepted_at__isnull=True
    )
    email = invitation.email
    invitation.delete()
    messages.success(request, f"The invitation for {email} was revoked.")
    return redirect("team_list")


@admin_required
@require_POST
def member_set_active(request, pk):
    member = get_object_or_404(User, pk=pk, firm=request.user.firm)
    if member.pk == request.user.pk:
        messages.error(request, "You can't deactivate your own account.")
        return redirect("team_list")
    member.is_active = request.POST.get("active") == "1"
    member.save(update_fields=["is_active"])
    state = "reactivated" if member.is_active else "deactivated"
    messages.success(request, f"{member.display_name} was {state}.")
    return redirect("team_list")


@admin_required
@require_POST
def member_set_role(request, pk):
    member = get_object_or_404(User, pk=pk, firm=request.user.firm)
    if member.pk == request.user.pk:
        messages.error(request, "You can't change your own role.")
        return redirect("team_list")
    role = request.POST.get("role", "")
    if role not in dict(User.ROLE_CHOICES):
        messages.error(request, "Unknown role.")
        return redirect("team_list")
    member.role = role
    member.save(update_fields=["role"])
    messages.success(request, f"{member.display_name} is now {member.get_role_display().lower()}.")
    return redirect("team_list")


def accept_invite(request, token):
    """Public page: the person opens their invitation link and sets a password."""
    invitation = get_object_or_404(Invitation, token=token)
    if not invitation.is_pending:
        return render(request, "accounts/invite_invalid.html", status=410)
    form = AcceptInviteForm(request.POST or None, invitation=invitation)
    if request.method == "POST" and form.is_valid():
        try:
            user = form.save()
        except InvitationUnavailable:
            return render(request, "accounts/invite_invalid.html", status=410)
        login(request, user)
        messages.success(request, f"Welcome to {user.firm.name}.")
        return redirect("dashboard")
    return render(request, "accounts/accept_invite.html", {"form": form, "invitation": invitation})


class AccountPasswordChangeView(SuccessMessageMixin, PasswordChangeView):
    template_name = "accounts/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("dashboard")
    success_message = "Your password was changed."
