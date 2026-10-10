from django.utils import timezone

from .models import ChatSeen, Message


def seen_map(user):
    return {s.project_id: s.last_seen for s in ChatSeen.objects.filter(user=user)}


def last_seen_for(user, project):
    """When this user last read the project's thread (never earlier than when they joined)."""
    seen = ChatSeen.objects.filter(user=user, project=project).first()
    baseline = user.date_joined
    return max(seen.last_seen, baseline) if seen else baseline


def mark_seen(user, project):
    ChatSeen.objects.update_or_create(
        user=user, project=project, defaults={"last_seen": timezone.now()}
    )


def unread_counts(user):
    """{project_id: number of messages from other people that this user has not read}."""
    seen = seen_map(user)
    baseline = user.date_joined
    rows = (
        Message.objects.filter(firm_id=user.firm_id, created_at__gt=baseline)
        .exclude(author=user)
        .values_list("project_id", "created_at")
    )
    counts = {}
    for project_id, created_at in rows:
        last = max(seen.get(project_id, baseline), baseline)
        if created_at > last:
            counts[project_id] = counts.get(project_id, 0) + 1
    return counts
