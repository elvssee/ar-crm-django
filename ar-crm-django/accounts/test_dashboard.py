from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Firm, User
from activities.models import Activity, FollowUp
from clients.models import Client
from discussions.models import Message
from drawings.models import Drawing
from projects.models import Project

PASSWORD = "Sturdy-pass-2026"


class DashboardTestCase(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(name="Alpha Architects")
        self.admin = User.objects.create_user(
            email="boss@alpha.example", password=PASSWORD, firm=self.firm, role=User.ROLE_ADMIN
        )
        self.junior = User.objects.create_user(
            email="junior@alpha.example", password=PASSWORD, firm=self.firm, role=User.ROLE_MEMBER
        )
        self.nair = Client.objects.create(firm=self.firm, name="Mr Nair")
        self.today = timezone.localdate()

        self.other_firm = Firm.objects.create(name="Beta Studio")
        self.other_admin = User.objects.create_user(
            email="boss@beta.example", password=PASSWORD, firm=self.other_firm, role=User.ROLE_ADMIN
        )
        self.other_client = Client.objects.create(firm=self.other_firm, name="Beta client")

    def login(self, email):
        self.assertTrue(self.client.login(username=email, password=PASSWORD))

    def project(self, title, stage, firm=None, client=None):
        return Project.objects.create(
            firm=firm or self.firm, client=client or self.nair, title=title, stage=stage
        )

    def seed_pipeline(self):
        self.project("Enquiry A", "enquiry")
        self.project("Proposal A", "proposal")
        self.project("Proposal B", "proposal")
        self.project("Design A", "design")
        self.project("Built A", "completed")


class MetricsTests(DashboardTestCase):
    def test_login_required(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_empty_firm_dashboard_renders(self):
        self.login("boss@alpha.example")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_projects"], 0)
        self.assertFalse(response.context["has_projects"])

    def test_pipeline_numbers(self):
        self.seed_pipeline()
        self.login("boss@alpha.example")
        context = self.client.get(reverse("dashboard")).context
        self.assertEqual(context["active_projects"], 4)  # completed work is excluded
        self.assertEqual(context["completed_projects"], 1)
        self.assertEqual(context["open_proposals"], 2)
        counts = {s["value"]: s["count"] for s in context["stages"]}
        self.assertEqual(counts, {"enquiry": 1, "proposal": 2, "design": 1, "construction": 0, "completed": 1})

    def test_other_firms_projects_are_not_counted(self):
        self.seed_pipeline()
        self.project("Beta big job", "design", firm=self.other_firm, client=self.other_client)
        self.login("boss@alpha.example")
        self.assertEqual(self.client.get(reverse("dashboard")).context["active_projects"], 4)

    def test_no_money_is_shown_anywhere_on_the_dashboard(self):
        project = self.project("Priced job", "proposal")
        project.estimated_fee = 123456
        project.save()
        for email in ("boss@alpha.example", "junior@alpha.example"):
            self.client.logout()
            self.login(email)
            response = self.client.get(reverse("dashboard"))
            self.assertNotContains(response, "₹")
            self.assertNotContains(response, "123,456")
            self.assertNotContains(response, "Pipeline value")


class FollowUpNumbersTests(DashboardTestCase):
    def setUp(self):
        super().setUp()
        villa = self.project("Villa", "design")

        def fu(note, due, who, done=False):
            return FollowUp.objects.create(
                firm=self.firm, project=villa, note=note, due_date=due, assigned_to=who, done=done
            )

        fu("Junior overdue", self.today - timedelta(days=2), self.junior)
        fu("Junior today", self.today, self.junior)
        fu("Boss overdue", self.today - timedelta(days=1), self.admin)
        fu("Boss later", self.today + timedelta(days=4), self.admin)
        fu("Finished", self.today - timedelta(days=9), self.junior, done=True)

    def test_admin_sees_firm_wide_counts(self):
        self.login("boss@alpha.example")
        context = self.client.get(reverse("dashboard")).context
        self.assertEqual(context["followup_scope"], "firm")
        self.assertEqual(context["followup_overdue"], 2)
        self.assertEqual(context["followup_today"], 1)

    def test_member_sees_only_own_counts_and_list(self):
        self.login("junior@alpha.example")
        response = self.client.get(reverse("dashboard"))
        context = response.context
        self.assertEqual(context["followup_scope"], "mine")
        self.assertEqual(context["followup_overdue"], 1)
        self.assertEqual(context["followup_today"], 1)
        self.assertContains(response, "Junior overdue")
        self.assertNotContains(response, "Boss overdue")
        self.assertNotContains(response, "Finished")


class RecentActivityTests(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.villa = self.project("Villa", "design")

    def test_feed_combines_drawings_messages_and_activities_newest_first(self):
        drawing = Drawing.objects.create(firm=self.firm, project=self.villa, title="Plan A", uploaded_by=self.junior)
        message = Message.objects.create(firm=self.firm, project=None, author=self.junior, body="Check the stairs")
        activity = Activity.objects.create(
            firm=self.firm, client=self.nair, project=self.villa, kind="call",
            summary="Called Mr Nair", created_by=self.admin,
        )
        # Fixed times, so the order never depends on the clock's resolution (Windows is coarse).
        now = timezone.now()
        Drawing.objects.filter(pk=drawing.pk).update(created_at=now - timedelta(minutes=3))
        Message.objects.filter(pk=message.pk).update(created_at=now - timedelta(minutes=2))
        Activity.objects.filter(pk=activity.pk).update(created_at=now - timedelta(minutes=1))
        self.login("boss@alpha.example")
        recent = self.client.get(reverse("dashboard")).context["recent"]
        self.assertEqual([item["label"] for item in recent], ["Call", "Message", "Drawing"])

    def test_team_chat_message_appears_in_feed(self):
        Message.objects.create(firm=self.firm, project=None, author=self.junior, body="Lunch at one?")
        self.login("boss@alpha.example")
        recent = self.client.get(reverse("dashboard")).context["recent"]
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["text"], "Team chat: Lunch at one?")
        self.assertEqual(recent[0]["url"], reverse("dashboard") + "#discussions")

    def test_old_project_thread_messages_are_not_in_the_feed(self):
        Message.objects.create(firm=self.firm, project=self.villa, author=self.junior, body="Old thread note")
        self.login("boss@alpha.example")
        self.assertEqual(self.client.get(reverse("dashboard")).context["recent"], [])

    def test_feed_excludes_other_firms(self):
        beta_project = self.project("Beta job", "design", firm=self.other_firm, client=self.other_client)
        Message.objects.create(firm=self.other_firm, project=None, author=self.other_admin, body="Beta secret")
        self.login("boss@alpha.example")
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, "Beta secret")
        self.assertEqual(response.context["recent"], [])

    def test_new_drawings_counts_uploads_by_others_only(self):
        Drawing.objects.create(firm=self.firm, project=self.villa, title="Plan A", uploaded_by=self.junior)
        Drawing.objects.create(firm=self.firm, project=self.villa, title="Plan B", uploaded_by=self.admin)
        self.login("boss@alpha.example")
        self.assertEqual(self.client.get(reverse("dashboard")).context["new_drawings"], 1)
