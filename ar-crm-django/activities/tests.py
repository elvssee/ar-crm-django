from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Firm, User
from clients.models import Client
from projects.models import Project

from .models import Activity, FollowUp

PASSWORD = "Sturdy-pass-2026"


class ActivityTestCase(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(name="Alpha Architects")
        self.admin = User.objects.create_user(
            email="boss@alpha.example", password=PASSWORD, firm=self.firm, role=User.ROLE_ADMIN
        )
        self.junior = User.objects.create_user(
            email="junior@alpha.example", password=PASSWORD, firm=self.firm, role=User.ROLE_MEMBER
        )
        self.nair = Client.objects.create(firm=self.firm, name="Mr Nair")
        self.menon = Client.objects.create(firm=self.firm, name="Mrs Menon")
        self.villa = Project.objects.create(firm=self.firm, client=self.nair, title="Nair villa")
        self.clinic = Project.objects.create(firm=self.firm, client=self.menon, title="Menon clinic")

        self.other_firm = Firm.objects.create(name="Beta Studio")
        self.other_admin = User.objects.create_user(
            email="boss@beta.example", password=PASSWORD, firm=self.other_firm, role=User.ROLE_ADMIN
        )
        self.other_client = Client.objects.create(firm=self.other_firm, name="Beta client")
        self.other_project = Project.objects.create(
            firm=self.other_firm, client=self.other_client, title="Beta project"
        )
        self.today = timezone.localdate()

    def login(self, email):
        self.assertTrue(self.client.login(username=email, password=PASSWORD))

    def log(self, **overrides):
        data = {
            "client": self.nair.pk, "project": self.villa.pk, "kind": "call",
            "summary": "Called about the site plan", "details": "He will send the survey.",
            "occurred_on": self.today.isoformat(),
        }
        data.update(overrides)
        return self.client.post(reverse("activity_create"), data)

    def make_activity(self, created_by=None, **kwargs):
        defaults = dict(firm=self.firm, client=self.nair, project=self.villa, kind="call",
                        summary="Earlier call", created_by=created_by)
        defaults.update(kwargs)
        return Activity.objects.create(**defaults)

    def make_followup(self, assigned_to=None, due=None, **kwargs):
        defaults = dict(
            firm=self.firm, project=self.villa, note="Send revised quote",
            due_date=due or self.today, assigned_to=assigned_to or self.junior, created_by=self.admin,
        )
        defaults.update(kwargs)
        return FollowUp.objects.create(**defaults)


class ActivityLogTests(ActivityTestCase):
    def test_login_required(self):
        response = self.client.get(reverse("activity_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_log_activity_sets_firm_and_author(self):
        self.login("junior@alpha.example")
        response = self.log(firm=self.other_firm.pk)
        self.assertRedirects(response, reverse("activity_list"))
        activity = Activity.objects.get()
        self.assertEqual(activity.firm, self.firm)
        self.assertEqual(activity.created_by, self.junior)
        self.assertEqual(activity.project, self.villa)

    def test_project_may_be_left_empty(self):
        self.login("junior@alpha.example")
        self.log(project="", kind="note", summary="General note")
        self.assertIsNone(Activity.objects.get().project)

    def test_project_must_belong_to_chosen_client(self):
        self.login("junior@alpha.example")
        self.log(client=self.nair.pk, project=self.clinic.pk)
        self.assertEqual(Activity.objects.count(), 0)

    def test_other_firms_client_and_project_are_rejected(self):
        self.login("junior@alpha.example")
        self.log(client=self.other_client.pk, project="")
        self.log(client=self.nair.pk, project=self.other_project.pk)
        self.assertEqual(Activity.objects.count(), 0)

    def test_unknown_kind_and_missing_summary_are_rejected(self):
        self.login("junior@alpha.example")
        self.log(kind="telepathy")
        self.log(summary="")
        self.assertEqual(Activity.objects.count(), 0)

    def test_form_is_prefilled_from_project(self):
        self.login("junior@alpha.example")
        response = self.client.get(reverse("activity_create"), {"project": self.villa.pk})
        form = response.context["form"]
        self.assertEqual(form.initial["client"], self.nair.pk)
        self.assertEqual(form.initial["project"], self.villa.pk)

    def test_list_filters_by_client_and_kind(self):
        self.make_activity(summary="Nair call")
        self.make_activity(client=self.menon, project=self.clinic, kind="meeting", summary="Menon meeting")
        self.login("boss@alpha.example")
        response = self.client.get(reverse("activity_list"), {"client": self.menon.pk})
        self.assertContains(response, "Menon meeting")
        self.assertNotContains(response, "Nair call")
        response = self.client.get(reverse("activity_list"), {"kind": "call"})
        self.assertContains(response, "Nair call")
        self.assertNotContains(response, "Menon meeting")

    def test_next_redirect_stays_on_this_site(self):
        self.login("junior@alpha.example")
        project_page = reverse("project_activity", args=[self.villa.pk])
        response = self.log(next=project_page)
        self.assertRedirects(response, project_page)
        response = self.log(next="https://evil.example/steal", summary="Second")
        self.assertRedirects(response, reverse("activity_list"))

    def test_project_activity_page_shows_history_only(self):
        self.make_activity(summary="Site measured")
        self.make_followup(note="Chase the survey")
        self.login("junior@alpha.example")
        response = self.client.get(reverse("project_activity", args=[self.villa.pk]))
        self.assertContains(response, "Site measured")
        self.assertNotContains(response, "Chase the survey")
        self.assertContains(response, reverse("project_followups", args=[self.villa.pk]))
        self.assertContains(response, reverse("project_activity_create", args=[self.villa.pk]))


class ProjectActivityLogTests(ActivityTestCase):
    def url(self, project=None):
        return reverse("project_activity_create", args=[(project or self.villa).pk])

    def test_form_shows_the_project_as_heading_and_has_no_project_or_client_field(self):
        self.login("junior@alpha.example")
        response = self.client.get(self.url())
        self.assertContains(response, "Nair villa")
        self.assertContains(response, "Mr Nair")
        self.assertNotIn("project", response.context["form"].fields)
        self.assertNotIn("client", response.context["form"].fields)

    def test_activity_is_saved_to_this_project_and_its_client(self):
        self.login("junior@alpha.example")
        project_page = reverse("project_activity", args=[self.villa.pk])
        response = self.client.post(self.url(), {
            "kind": "call", "summary": "Called about the plan", "details": "",
            "occurred_on": self.today.isoformat(), "next": project_page,
            # attempts to point it somewhere else are ignored
            "project": self.clinic.pk, "client": self.menon.pk,
        })
        self.assertRedirects(response, project_page)
        activity = Activity.objects.get()
        self.assertEqual(activity.project, self.villa)
        self.assertEqual(activity.client, self.nair)
        self.assertEqual(activity.firm, self.firm)
        self.assertEqual(activity.created_by, self.junior)

    def test_default_redirect_is_the_project_page(self):
        self.login("junior@alpha.example")
        response = self.client.post(self.url(), {
            "kind": "note", "summary": "Quick note", "occurred_on": self.today.isoformat(),
        })
        self.assertRedirects(response, reverse("project_activity", args=[self.villa.pk]))

    def test_other_firms_project_is_404(self):
        self.login("junior@alpha.example")
        self.assertEqual(self.client.get(self.url(self.other_project)).status_code, 404)
        self.assertEqual(self.client.post(self.url(self.other_project), {
            "kind": "call", "summary": "x", "occurred_on": self.today.isoformat(),
        }).status_code, 404)
        self.assertEqual(Activity.objects.count(), 0)

    def test_editing_a_project_activity_keeps_its_project(self):
        activity = self.make_activity(created_by=self.junior)
        self.login("junior@alpha.example")
        response = self.client.get(reverse("activity_edit", args=[activity.pk]))
        self.assertNotIn("project", response.context["form"].fields)
        self.client.post(reverse("activity_edit", args=[activity.pk]), {
            "kind": "meeting", "summary": "Moved", "occurred_on": self.today.isoformat(),
            "project": self.clinic.pk, "client": self.menon.pk,
        })
        activity.refresh_from_db()
        self.assertEqual(activity.kind, "meeting")
        self.assertEqual(activity.project, self.villa)
        self.assertEqual(activity.client, self.nair)


class ActivityPermissionTests(ActivityTestCase):
    def test_junior_cannot_edit_or_delete_others_activity(self):
        activity = self.make_activity(created_by=self.admin)
        self.login("junior@alpha.example")
        self.assertEqual(self.client.get(reverse("activity_edit", args=[activity.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("activity_delete", args=[activity.pk])).status_code, 403)
        self.assertTrue(Activity.objects.filter(pk=activity.pk).exists())

    def test_junior_can_edit_and_delete_own_activity(self):
        activity = self.make_activity(created_by=self.junior)
        self.login("junior@alpha.example")
        self.client.post(reverse("activity_edit", args=[activity.pk]), {
            "client": self.nair.pk, "project": self.villa.pk, "kind": "meeting",
            "summary": "Now a meeting", "details": "", "occurred_on": self.today.isoformat(),
        })
        activity.refresh_from_db()
        self.assertEqual(activity.kind, "meeting")
        self.client.post(reverse("activity_delete", args=[activity.pk]))
        self.assertFalse(Activity.objects.filter(pk=activity.pk).exists())

    def test_admin_can_delete_any_activity(self):
        activity = self.make_activity(created_by=self.junior)
        self.login("boss@alpha.example")
        self.client.post(reverse("activity_delete", args=[activity.pk]))
        self.assertFalse(Activity.objects.filter(pk=activity.pk).exists())


class FollowUpTests(ActivityTestCase):
    def create(self, project=None, **overrides):
        data = {
            "note": "Send revised quote",
            "due_date": self.today.isoformat(), "assigned_to": self.junior.pk,
        }
        data.update(overrides)
        return self.client.post(reverse("project_followup_create", args=[(project or self.villa).pk]), data)

    def test_create_followup(self):
        self.login("boss@alpha.example")
        response = self.create()
        self.assertRedirects(response, reverse("project_followups", args=[self.villa.pk]))
        followup = FollowUp.objects.get()
        self.assertEqual(followup.project, self.villa)
        self.assertEqual(followup.firm, self.firm)
        self.assertEqual(followup.created_by, self.admin)
        self.assertEqual(followup.assigned_to, self.junior)

    def test_cannot_assign_to_someone_in_another_firm(self):
        self.login("boss@alpha.example")
        self.create(assigned_to=self.other_admin.pk)
        self.assertEqual(FollowUp.objects.count(), 0)

    def test_cannot_use_another_firms_project(self):
        self.login("boss@alpha.example")
        response = self.create(project=self.other_project)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(FollowUp.objects.count(), 0)

    def test_project_cannot_be_changed_from_the_form(self):
        self.login("boss@alpha.example")
        response = self.client.get(reverse("project_followup_create", args=[self.villa.pk]))
        self.assertContains(response, "Nair villa")
        self.assertNotIn("project", response.context["form"].fields)
        self.client.post(reverse("project_followup_create", args=[self.villa.pk]), {
            "note": "Sneaky", "due_date": self.today.isoformat(), "assigned_to": self.junior.pk,
            "project": self.clinic.pk,  # an attempt to point it at another project is ignored
        })
        self.assertEqual(FollowUp.objects.get().project, self.villa)

    def test_editing_keeps_the_project(self):
        followup = self.make_followup(assigned_to=self.junior)
        self.login("boss@alpha.example")
        response = self.client.get(reverse("followup_edit", args=[followup.pk]))
        self.assertNotIn("project", response.context["form"].fields)
        response = self.client.post(reverse("followup_edit", args=[followup.pk]), {
            "note": "Changed note", "due_date": self.today.isoformat(), "assigned_to": self.junior.pk,
            "project": self.clinic.pk,
        })
        self.assertRedirects(response, reverse("project_followups", args=[self.villa.pk]))
        followup.refresh_from_db()
        self.assertEqual(followup.note, "Changed note")
        self.assertEqual(followup.project, self.villa)

    def test_project_page_lists_only_that_projects_followups(self):
        self.make_followup(note="Villa task")
        self.make_followup(note="Clinic task", project=self.clinic)
        done = self.make_followup(note="Villa finished task")
        self.login("junior@alpha.example")
        self.client.post(reverse("followup_toggle", args=[done.pk]))
        response = self.client.get(reverse("project_followups", args=[self.villa.pk]))
        self.assertContains(response, "Nair villa")
        self.assertContains(response, "Villa task")
        self.assertContains(response, "Villa finished task")
        self.assertContains(response, "Add follow-up")
        self.assertNotContains(response, "Clinic task")

    def test_toggle_and_delete_return_to_the_projects_page(self):
        followup = self.make_followup(assigned_to=self.junior)
        self.login("junior@alpha.example")
        page = reverse("project_followups", args=[self.villa.pk])
        self.assertRedirects(self.client.post(reverse("followup_toggle", args=[followup.pk])), page)
        self.assertRedirects(self.client.post(reverse("followup_delete", args=[followup.pk])), page)

    def test_other_firm_cannot_open_the_project_followup_pages(self):
        self.login("boss@beta.example")
        self.assertEqual(self.client.get(reverse("project_followups", args=[self.villa.pk])).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("project_followup_create", args=[self.villa.pk])).status_code, 404
        )

    def test_all_projects_list_has_no_add_button_and_no_global_create_page(self):
        self.login("boss@alpha.example")
        self.assertNotContains(self.client.get(reverse("followup_list")), "Add follow-up")
        self.assertEqual(self.client.get("/followups/new/").status_code, 404)


class NavigationTests(ActivityTestCase):
    def test_top_bar_has_no_followups_tab_but_project_rows_link_to_followups(self):
        self.login("boss@alpha.example")
        response = self.client.get(reverse("project_list"))
        self.assertNotContains(response, 'href="%s"' % reverse("followup_list"))
        self.assertContains(response, reverse("project_followups", args=[self.villa.pk]))

    def test_dashboard_still_links_to_the_all_projects_followup_list(self):
        self.make_followup(assigned_to=self.admin, due=self.today)
        self.login("boss@alpha.example")
        self.assertContains(self.client.get(reverse("dashboard")), reverse("followup_list"))

    def test_overdue_and_due_today_flags(self):
        overdue = self.make_followup(due=self.today - timedelta(days=2))
        today = self.make_followup(due=self.today)
        later = self.make_followup(due=self.today + timedelta(days=3))
        self.assertTrue(overdue.is_overdue)
        self.assertFalse(overdue.is_due_today)
        self.assertTrue(today.is_due_today)
        self.assertFalse(today.is_overdue)
        self.assertFalse(later.is_overdue or later.is_due_today)

    def test_list_groups_and_scope(self):
        self.make_followup(note="Late task", due=self.today - timedelta(days=1), assigned_to=self.junior)
        self.make_followup(note="Boss task", due=self.today + timedelta(days=5), assigned_to=self.admin)
        self.login("junior@alpha.example")
        everyone = self.client.get(reverse("followup_list"))
        self.assertContains(everyone, "Late task")
        self.assertContains(everyone, "Boss task")
        mine = self.client.get(reverse("followup_list"), {"scope": "mine"})
        self.assertContains(mine, "Late task")
        self.assertNotContains(mine, "Boss task")

    def test_assignee_can_mark_done_and_reopen(self):
        followup = self.make_followup(assigned_to=self.junior)
        self.login("junior@alpha.example")
        self.client.post(reverse("followup_toggle", args=[followup.pk]))
        followup.refresh_from_db()
        self.assertTrue(followup.done)
        self.assertIsNotNone(followup.done_at)
        done_page = self.client.get(reverse("followup_list"), {"status": "done"})
        self.assertContains(done_page, "Send revised quote")
        self.client.post(reverse("followup_toggle", args=[followup.pk]))
        followup.refresh_from_db()
        self.assertFalse(followup.done)
        self.assertIsNone(followup.done_at)

    def test_unrelated_member_cannot_change_followup(self):
        other_junior = User.objects.create_user(
            email="other@alpha.example", password=PASSWORD, firm=self.firm, role=User.ROLE_MEMBER
        )
        followup = self.make_followup(assigned_to=self.junior)
        self.login("other@alpha.example")
        self.assertEqual(self.client.post(reverse("followup_toggle", args=[followup.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("followup_delete", args=[followup.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("followup_edit", args=[followup.pk])).status_code, 403)
        followup.refresh_from_db()
        self.assertFalse(followup.done)
        self.assertEqual(other_junior.firm, self.firm)

    def test_toggle_requires_post(self):
        followup = self.make_followup()
        self.login("boss@alpha.example")
        self.assertEqual(self.client.get(reverse("followup_toggle", args=[followup.pk])).status_code, 405)

    def test_admin_can_delete_followup(self):
        followup = self.make_followup()
        self.login("boss@alpha.example")
        self.client.post(reverse("followup_delete", args=[followup.pk]))
        self.assertEqual(FollowUp.objects.count(), 0)


class DashboardTests(ActivityTestCase):
    def test_dashboard_shows_my_overdue_and_due_today_only(self):
        self.make_followup(note="My overdue job", due=self.today - timedelta(days=3), assigned_to=self.junior)
        self.make_followup(note="My job today", due=self.today, assigned_to=self.junior)
        self.make_followup(note="My far future job", due=self.today + timedelta(days=9), assigned_to=self.junior)
        self.make_followup(note="Boss own job", due=self.today, assigned_to=self.admin)
        self.make_followup(note="Finished job", due=self.today, assigned_to=self.junior, done=True)
        self.login("junior@alpha.example")
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "My overdue job")
        self.assertContains(response, "My job today")
        self.assertNotContains(response, "My far future job")
        self.assertNotContains(response, "Boss own job")
        self.assertNotContains(response, "Finished job")


class TenantIsolationTests(ActivityTestCase):
    def setUp(self):
        super().setUp()
        self.secret_activity = self.make_activity(created_by=self.junior, summary="Alpha secret call")
        self.secret_followup = self.make_followup(note="Alpha secret task")
        self.login("boss@beta.example")

    def test_other_firm_sees_nothing(self):
        self.assertNotContains(self.client.get(reverse("activity_list")), "Alpha secret call")
        self.assertNotContains(self.client.get(reverse("followup_list")), "Alpha secret task")
        dashboard = self.client.get(reverse("dashboard"))
        self.assertNotContains(dashboard, "Alpha secret task")

    def test_other_firm_cannot_open_project_page(self):
        self.assertEqual(self.client.get(reverse("project_activity", args=[self.villa.pk])).status_code, 404)

    def test_other_firm_cannot_edit_or_delete(self):
        self.assertEqual(self.client.get(reverse("activity_edit", args=[self.secret_activity.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("activity_delete", args=[self.secret_activity.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("followup_toggle", args=[self.secret_followup.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("followup_delete", args=[self.secret_followup.pk])).status_code, 404)
        self.assertTrue(Activity.objects.filter(pk=self.secret_activity.pk).exists())
        self.assertTrue(FollowUp.objects.filter(pk=self.secret_followup.pk, done=False).exists())
