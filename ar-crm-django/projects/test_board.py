from django.test import TestCase
from django.urls import reverse

from accounts.models import Firm, User
from clients.models import Client

from .models import Project

PASSWORD = "Sturdy-pass-2026"


def make_user(email, firm_name):
    firm = Firm.objects.create(name=firm_name)
    user = User.objects.create_user(email=email, password=PASSWORD, firm=firm, role=User.ROLE_ADMIN)
    return user, firm


class BoardTests(TestCase):
    def setUp(self):
        self.user, self.firm = make_user("a@alpha.example", "Alpha Architects")
        self.nair = Client.objects.create(firm=self.firm, name="Mr Nair")
        self.project = Project.objects.create(
            firm=self.firm, client=self.nair, title="Nair villa", stage="enquiry",
            estimated_fee=1500000,
        )
        self.client.login(username="a@alpha.example", password=PASSWORD)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("project_board"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_board_shows_project_with_client(self):
        response = self.client.get(reverse("project_board"))
        self.assertContains(response, "Nair villa")
        self.assertContains(response, "Mr Nair")

    def test_move_changes_stage(self):
        response = self.client.post(reverse("project_move", args=[self.project.pk]), {"stage": "design"})
        self.assertRedirects(response, reverse("project_board"))
        self.project.refresh_from_db()
        self.assertEqual(self.project.stage, "design")

    def test_move_via_ajax_returns_json(self):
        response = self.client.post(
            reverse("project_move", args=[self.project.pk]),
            {"stage": "proposal"},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "stage": "proposal"})

    def test_move_requires_post(self):
        response = self.client.get(reverse("project_move", args=[self.project.pk]))
        self.assertEqual(response.status_code, 405)

    def test_invalid_stage_is_rejected(self):
        response = self.client.post(reverse("project_move", args=[self.project.pk]), {"stage": "nonsense"})
        self.assertEqual(response.status_code, 400)
        self.project.refresh_from_db()
        self.assertEqual(self.project.stage, "enquiry")


class BoardTenantIsolationTests(TestCase):
    def setUp(self):
        self.user_a, self.firm_a = make_user("a@alpha.example", "Alpha Architects")
        self.user_b, self.firm_b = make_user("b@beta.example", "Beta Studio")
        client_a = Client.objects.create(firm=self.firm_a, name="Alpha Client")
        self.secret = Project.objects.create(
            firm=self.firm_a, client=client_a, title="Alpha Secret Project", stage="enquiry"
        )
        self.client.login(username="b@beta.example", password=PASSWORD)

    def test_other_firm_does_not_see_project_on_board(self):
        self.assertNotContains(self.client.get(reverse("project_board")), "Alpha Secret Project")

    def test_other_firm_cannot_move_project(self):
        response = self.client.post(reverse("project_move", args=[self.secret.pk]), {"stage": "completed"})
        self.assertEqual(response.status_code, 404)
        self.secret.refresh_from_db()
        self.assertEqual(self.secret.stage, "enquiry")
