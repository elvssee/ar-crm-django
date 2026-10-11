"""Numbers and lists for the dashboard. Everything here is limited to the user's own firm."""

from django.db.models import Count
from django.urls import reverse
from django.utils import timezone


def build_dashboard(user):
    # Imported here so this module can be loaded before every app is ready.
    from activities.models import Activity, FollowUp
    from clients.models import Client
    from discussions.models import Message
    from discussions.services import unread_counts
    from drawings.models import Drawing
    from drawings.views import annotate as annotate_drawings
    from projects.models import Project

    firm = user.firm
    today = timezone.localdate()

    # ---- projects and pipeline
    rows = Project.objects.filter(firm=firm).values("stage").annotate(n=Count("id"))
    by_stage = {row["stage"]: row for row in rows}
    biggest = max((row["n"] for row in rows), default=0)
    stages = []
    for value, label in Project.STAGE_CHOICES:
        row = by_stage.get(value, {"n": 0})
        stages.append({
            "value": value,
            "label": label,
            "count": row["n"],
            "percent": round(100 * row["n"] / biggest) if biggest else 0,
        })
    open_stages = [s for s in stages if s["value"] != Project.STAGE_COMPLETED]
    proposals = by_stage.get(Project.STAGE_PROPOSAL, {"n": 0})

    # ---- follow-ups: whole firm for admins, only your own for everyone else
    open_followups = FollowUp.objects.filter(firm=firm, done=False)
    mine = open_followups.filter(assigned_to=user)
    counted = open_followups if user.is_firm_admin else mine
    due_followups = list(
        mine.filter(due_date__lte=today).select_related("project").order_by("due_date", "id")[:8]
    )

    # ---- drawings and messages that are new to this user
    recent_drawings = list(
        Drawing.objects.filter(firm=firm).select_related("project", "uploaded_by").order_by("-created_at")[:8]
    )
    annotate_drawings(recent_drawings, user)

    context = {
        "firm": firm,
        "active_projects": sum(s["count"] for s in open_stages),
        "completed_projects": by_stage.get(Project.STAGE_COMPLETED, {"n": 0})["n"],
        "open_proposals": proposals["n"],
        "stages": stages,
        "has_projects": biggest > 0,
        "clients_count": Client.objects.filter(firm=firm).count(),
        "followup_scope": "firm" if user.is_firm_admin else "mine",
        "followup_overdue": counted.filter(due_date__lt=today).count(),
        "followup_today": counted.filter(due_date=today).count(),
        "due_followups": due_followups,
        "new_drawings": sum(1 for d in recent_drawings if d.is_new),
        "unread_messages": sum(unread_counts(user).values()),
    }

    # ---- recent activity: the latest few things from drawings, messages and the activity log
    feed = []
    for drawing in recent_drawings:
        feed.append({
            "when": drawing.created_at, "label": "Drawing",
            "text": f"{drawing.title} uploaded to {drawing.project.title}",
            "who": drawing.uploaded_by.display_name if drawing.uploaded_by else "Former member",
            "url": reverse("project_drawings", args=[drawing.project_id]),
        })
    for message in Message.objects.filter(firm=firm, project__isnull=True).select_related("author").order_by("-id")[:8]:
        body = message.body or f"sent a file: {message.attachment_name}"
        text = body if len(body) <= 90 else body[:87] + "…"
        feed.append({
            "when": message.created_at, "label": "Message",
            "text": f"Team chat: {text}",
            "who": message.author.display_name if message.author else "Former member",
            "url": reverse("dashboard") + "#discussions",  # opens the discussions panel
        })
    for activity in Activity.objects.filter(firm=firm).select_related("client", "project", "created_by").order_by("-created_at")[:8]:
        feed.append({
            "when": activity.created_at, "label": activity.get_kind_display(),
            "text": f"{activity.summary} · {activity.client.name}",
            "who": activity.created_by.display_name if activity.created_by else "Former member",
            "url": (
                reverse("project_activity", args=[activity.project_id])
                if activity.project_id else reverse("activity_list")
            ),
        })
    feed.sort(key=lambda item: item["when"], reverse=True)
    context["recent"] = feed[:10]
    return context
