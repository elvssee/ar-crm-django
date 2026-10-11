from django.test import TestCase
from django.urls import reverse

from accounts.models import Firm, User
from clients.models import Client
from drawings.models import Drawing
from projects.models import Project

from .models import Message

PASSWORD = "Sturdy-pass-2026"
AJAX = {"x-requested-with": "XMLHttpRequest"}


class PanelTestCase(TestCase):
    def setUp(self):
        self.firm = Firm.objects.create(name="Alpha Architects")
        self.admin = User.objects.create_user(
            email="boss@alpha.example", password=PASSWORD, firm=self.firm, role=User.ROLE_ADMIN
        )
        self.junior = User.objects.create_user(
            email="junior@alpha.example", password=PASSWORD, firm=self.firm, role=User.ROLE_MEMBER
        )
        nair = Client.objects.create(firm=self.firm, name="Mr Nair")
        self.site1 = Project.objects.create(firm=self.firm, client=nair, title="Site 1")
        self.site2 = Project.objects.create(firm=self.firm, client=nair, title="Site 2")

        self.other_firm = Firm.objects.create(name="Beta Studio")
        self.other_admin = User.objects.create_user(
            email="boss@beta.example", password=PASSWORD, firm=self.other_firm, role=User.ROLE_ADMIN
        )

    def login(self, email):
        self.assertTrue(self.client.login(username=email, password=PASSWORD))

    def say(self, author, body, project=None, firm=None):
        return Message.objects.create(firm=firm or self.firm, project=project, author=author, body=body)


class DashboardButtonTests(PanelTestCase):
    def test_dashboard_has_button_and_panel_but_no_unread_text(self):
        self.say(self.junior, "Hello team")
        self.login("boss@alpha.example")
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "data-panel-open")
        self.assertContains(response, 'id="discussion-panel"')
        self.assertNotContains(response, "unread message")

    def test_button_badge_counts_unread(self):
        self.say(self.junior, "Hello team")
        self.login("boss@alpha.example")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["unread_total"], 1)


class PanelFragmentTests(PanelTestCase):
    def test_panel_endpoints_need_login(self):
        for name in ("panel_general", "discussion_unread"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn(reverse("login"), response.url)

    def test_team_chat_fragment_has_messages_and_send_url(self):
        self.say(self.junior, "Check the stairs")
        self.login("boss@alpha.example")
        response = self.client.get(reverse("panel_general"))
        self.assertContains(response, "Check the stairs")
        self.assertContains(response, reverse("general_send"))
        self.assertContains(response, "data-send-form")
        self.assertNotContains(response, "Attach a drawing")

    def test_unread_json_counts_only_the_team_chat(self):
        self.say(self.junior, "Old project thread message", project=self.site1)
        self.say(self.junior, "Two")
        self.login("boss@alpha.example")
        self.assertEqual(self.client.get(reverse("discussion_unread")).json(), {"total": 1})


class NoOtherDiscussionPagesTests(PanelTestCase):
    """Discussions exist only inside the dashboard panel."""

    def test_old_discussion_pages_are_gone(self):
        self.login("boss@alpha.example")
        for path in (
            "/discussions/", "/discussions/general/", "/discussions/panel/",
            f"/projects/{self.site1.pk}/discussion/", f"/discussions/panel/projects/{self.site1.pk}/",
        ):
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_project_pages_have_no_discussion_link(self):
        self.login("boss@alpha.example")
        for url in (
            reverse("project_list"), reverse("project_board"),
            reverse("project_drawings", args=[self.site1.pk]),
            reverse("project_activity", args=[self.site1.pk]),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertNotContains(response, "Discussion", msg_prefix=url)

    def test_top_bar_has_no_discussions_tab(self):
        self.login("boss@alpha.example")
        response = self.client.get(reverse("project_list"))
        self.assertNotContains(response, "Discussions")


class TeamChatTests(PanelTestCase):
    def test_send_to_team_chat_creates_message_without_project(self):
        self.login("junior@alpha.example")
        response = self.client.post(reverse("general_send"), {"body": "Who is free for the meeting?"}, headers=AJAX)
        self.assertEqual(response.status_code, 201)
        message = Message.objects.get()
        self.assertIsNone(message.project)
        self.assertEqual(message.firm, self.firm)
        self.assertEqual(message.author, self.junior)

    def test_drawing_is_ignored_in_team_chat(self):
        drawing = Drawing.objects.create(firm=self.firm, project=self.site1, title="Plan")
        self.login("junior@alpha.example")
        self.client.post(reverse("general_send"), {"body": "hi", "drawing": drawing.pk}, headers=AJAX)
        self.assertIsNone(Message.objects.get().drawing)

    def test_empty_message_is_rejected(self):
        self.login("junior@alpha.example")
        response = self.client.post(reverse("general_send"), {"body": "  "}, headers=AJAX)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Message.objects.count(), 0)

    def test_poll_returns_only_newer_team_messages_and_not_old_project_messages(self):
        first = self.say(self.admin, "First")
        self.say(self.admin, "Second")
        self.say(self.admin, "Only on site one", project=self.site1)
        self.login("junior@alpha.example")
        response = self.client.get(reverse("general_poll"), {"after": first.pk}, headers=AJAX)
        self.assertContains(response, "Second")
        self.assertNotContains(response, "First")
        self.assertNotContains(response, "Only on site one")

    def test_unread_clears_after_opening_team_chat(self):
        self.say(self.junior, "Anyone there?")
        self.login("boss@alpha.example")
        self.assertEqual(self.client.get(reverse("discussion_unread")).json(), {"total": 1})
        self.assertContains(self.client.get(reverse("panel_general")), "data-new-badge")
        self.assertEqual(self.client.get(reverse("discussion_unread")).json(), {"total": 0})

    def test_own_team_messages_are_never_unread(self):
        self.say(self.junior, "My own note")
        self.login("junior@alpha.example")
        self.assertEqual(self.client.get(reverse("discussion_unread")).json(), {"total": 0})


class DeleteInPanelTests(PanelTestCase):
    def test_ajax_delete_returns_json_and_removes_message(self):
        message = self.say(self.junior, "Oops")
        self.login("junior@alpha.example")
        response = self.client.post(reverse("discussion_delete", args=[message.pk]), headers=AJAX)
        self.assertEqual(response.json(), {"ok": True})
        self.assertFalse(Message.objects.filter(pk=message.pk).exists())

    def test_plain_delete_goes_back_to_the_dashboard(self):
        message = self.say(self.junior, "Oops")
        self.login("junior@alpha.example")
        response = self.client.post(reverse("discussion_delete", args=[message.pk]))
        self.assertRedirects(response, reverse("dashboard"))

    def test_junior_cannot_delete_bosses_team_message(self):
        message = self.say(self.admin, "Boss note")
        self.login("junior@alpha.example")
        response = self.client.post(reverse("discussion_delete", args=[message.pk]), headers=AJAX)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Message.objects.filter(pk=message.pk).exists())


class PanelTenantIsolationTests(PanelTestCase):
    def setUp(self):
        super().setUp()
        self.secret_team = self.say(self.junior, "Alpha team secret")
        self.login("boss@beta.example")

    def test_other_firm_sees_none_of_it_in_the_panel(self):
        self.assertNotContains(self.client.get(reverse("panel_general")), "Alpha team secret")
        self.assertEqual(self.client.get(reverse("discussion_unread")).json(), {"total": 0})
        self.assertEqual(self.client.get(reverse("general_poll"), {"after": 0}, headers=AJAX).content, b"")

    def test_other_firm_has_its_own_separate_team_chat(self):
        response = self.client.post(reverse("general_send"), {"body": "Beta hello"}, headers=AJAX)
        self.assertEqual(response.status_code, 201)
        beta = Message.objects.get(body="Beta hello")
        self.assertEqual(beta.firm, self.other_firm)
        self.client.logout()
        self.login("boss@alpha.example")
        self.assertNotContains(self.client.get(reverse("panel_general")), "Beta hello")

    def test_other_firm_cannot_delete_our_team_message(self):
        response = self.client.post(reverse("discussion_delete", args=[self.secret_team.pk]), headers=AJAX)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Message.objects.filter(pk=self.secret_team.pk).exists())
