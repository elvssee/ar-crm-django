from django.test import TestCase
from django.urls import reverse

from accounts.models import Firm, User

from .models import Client

PASSWORD = "Sturdy-pass-2026"


def make_user(email, firm_name):
    firm = Firm.objects.create(name=firm_name)
    user = User.objects.create_user(email=email, password=PASSWORD, firm=firm, role=User.ROLE_ADMIN)
    return user, firm


class ClientAccessTests(TestCase):
    def test_login_required(self):
        response = self.client.get(reverse("client_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_user_without_firm_is_forbidden(self):
        User.objects.create_superuser(email="root@example.com", password=PASSWORD)
        self.client.login(username="root@example.com", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("client_list")).status_code, 403)


class ClientCrudTests(TestCase):
    def setUp(self):
        self.user, self.firm = make_user("a@alpha.example", "Alpha Architects")
        self.client.login(username="a@alpha.example", password=PASSWORD)

    def test_create_sets_firm_from_user_and_ignores_posted_firm(self):
        other_firm = Firm.objects.create(name="Other Firm")
        self.client.post(
            reverse("client_create"),
            {"name": "Mr Nair", "phone": "999", "firm": other_firm.id},
        )
        created = Client.objects.get(name="Mr Nair")
        self.assertEqual(created.firm, self.firm)

    def test_list_edit_delete(self):
        obj = Client.objects.create(firm=self.firm, name="Mr Nair")
        self.assertContains(self.client.get(reverse("client_list")), "Mr Nair")

        self.client.post(reverse("client_edit", args=[obj.pk]), {"name": "Mr K Nair"})
        obj.refresh_from_db()
        self.assertEqual(obj.name, "Mr K Nair")

        self.client.post(reverse("client_delete", args=[obj.pk]))
        self.assertFalse(Client.objects.filter(pk=obj.pk).exists())

    def test_name_is_required(self):
        self.client.post(reverse("client_create"), {"name": ""})
        self.assertEqual(Client.objects.count(), 0)

    def test_search(self):
        Client.objects.create(firm=self.firm, name="Mr Nair", email="nair@example.com")
        Client.objects.create(firm=self.firm, name="Mrs Menon")
        response = self.client.get(reverse("client_list"), {"q": "menon"})
        self.assertContains(response, "Mrs Menon")
        self.assertNotContains(response, "Mr Nair")


class TenantIsolationTests(TestCase):
    """Firm B must never see or touch firm A's clients."""

    def setUp(self):
        self.user_a, self.firm_a = make_user("a@alpha.example", "Alpha Architects")
        self.user_b, self.firm_b = make_user("b@beta.example", "Beta Studio")
        self.secret = Client.objects.create(firm=self.firm_a, name="Alpha Secret Client")
        self.client.login(username="b@beta.example", password=PASSWORD)

    def test_other_firm_cannot_see_client_in_list(self):
        response = self.client.get(reverse("client_list"))
        self.assertNotContains(response, "Alpha Secret Client")

    def test_other_firm_cannot_search_for_client(self):
        response = self.client.get(reverse("client_list"), {"q": "Secret"})
        self.assertNotContains(response, "Alpha Secret Client")

    def test_other_firm_cannot_open_edit_page(self):
        response = self.client.get(reverse("client_edit", args=[self.secret.pk]))
        self.assertEqual(response.status_code, 404)

    def test_other_firm_cannot_edit_client(self):
        self.client.post(reverse("client_edit", args=[self.secret.pk]), {"name": "Hacked"})
        self.secret.refresh_from_db()
        self.assertEqual(self.secret.name, "Alpha Secret Client")

    def test_other_firm_cannot_delete_client(self):
        response = self.client.post(reverse("client_delete", args=[self.secret.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Client.objects.filter(pk=self.secret.pk).exists())
