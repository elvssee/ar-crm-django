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


class ProjectCrudTests(TestCase):
    def setUp(self):
        self.user, self.firm = make_user("a@alpha.example", "Alpha Architects")
        self.nair = Client.objects.create(firm=self.firm, name="Mr Nair")
        self.client.login(username="a@alpha.example", password=PASSWORD)

    def test_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("project_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_create_sets_firm_from_user_and_ignores_posted_firm(self):
        other_firm = Firm.objects.create(name="Other Firm")
        self.client.post(
            reverse("project_create"),
            {
                "client": self.nair.pk, "title": "Nair villa", "project_type": "residential",
                "stage": "enquiry", "firm": other_firm.pk,
            },
        )
        project = Project.objects.get(title="Nair villa")
        self.assertEqual(project.firm, self.firm)
        self.assertEqual(project.client, self.nair)

    def test_create_redirects_to_add_client_when_firm_has_no_clients(self):
        self.nair.delete()
        response = self.client.get(reverse("project_create"))
        self.assertRedirects(response, reverse("client_create"))

    def test_list_edit_delete(self):
        project = Project.objects.create(firm=self.firm, client=self.nair, title="Nair villa")
        self.assertContains(self.client.get(reverse("project_list")), "Nair villa")

        self.client.post(
            reverse("project_edit", args=[project.pk]),
            {"client": self.nair.pk, "title": "Nair villa phase 2", "project_type": "residential", "stage": "design"},
        )
        project.refresh_from_db()
        self.assertEqual(project.title, "Nair villa phase 2")
        self.assertEqual(project.stage, "design")

        self.client.post(reverse("project_delete", args=[project.pk]))
        self.assertFalse(Project.objects.filter(pk=project.pk).exists())

    def test_filter_by_stage_and_search(self):
        Project.objects.create(firm=self.firm, client=self.nair, title="Villa", stage="design")
        Project.objects.create(firm=self.firm, client=self.nair, title="Cafe", stage="enquiry")
        response = self.client.get(reverse("project_list"), {"stage": "design"})
        self.assertContains(response, "Villa")
        self.assertNotContains(response, "Cafe")
        response = self.client.get(reverse("project_list"), {"q": "nair"})
        self.assertContains(response, "Villa")
        self.assertContains(response, "Cafe")

    def test_client_with_projects_cannot_be_deleted(self):
        Project.objects.create(firm=self.firm, client=self.nair, title="Villa")
        response = self.client.post(reverse("client_delete", args=[self.nair.pk]), follow=True)
        self.assertTrue(Client.objects.filter(pk=self.nair.pk).exists())
        self.assertContains(response, "still has projects")


class ProjectTenantIsolationTests(TestCase):
    """Firm B must never see or touch firm A's projects or use firm A's clients."""

    def setUp(self):
        self.user_a, self.firm_a = make_user("a@alpha.example", "Alpha Architects")
        self.user_b, self.firm_b = make_user("b@beta.example", "Beta Studio")
        self.client_a = Client.objects.create(firm=self.firm_a, name="Alpha Client")
        self.client_b = Client.objects.create(firm=self.firm_b, name="Beta Client")
        self.secret = Project.objects.create(
            firm=self.firm_a, client=self.client_a, title="Alpha Secret Project"
        )
        self.client.login(username="b@beta.example", password=PASSWORD)

    def test_other_firm_cannot_see_project(self):
        self.assertNotContains(self.client.get(reverse("project_list")), "Alpha Secret Project")
        response = self.client.get(reverse("project_list"), {"q": "Secret"})
        self.assertNotContains(response, "Alpha Secret Project")

    def test_other_firm_cannot_open_edit_or_delete(self):
        self.assertEqual(self.client.get(reverse("project_edit", args=[self.secret.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("project_delete", args=[self.secret.pk])).status_code, 404)
        self.assertTrue(Project.objects.filter(pk=self.secret.pk).exists())

    def test_other_firm_cannot_edit_project(self):
        self.client.post(
            reverse("project_edit", args=[self.secret.pk]),
            {"client": self.client_b.pk, "title": "Hacked", "project_type": "other", "stage": "enquiry"},
        )
        self.secret.refresh_from_db()
        self.assertEqual(self.secret.title, "Alpha Secret Project")

    def test_cannot_create_project_for_another_firms_client(self):
        self.client.post(
            reverse("project_create"),
            {"client": self.client_a.pk, "title": "Sneaky", "project_type": "other", "stage": "enquiry"},
        )
        self.assertFalse(Project.objects.filter(title="Sneaky").exists())
