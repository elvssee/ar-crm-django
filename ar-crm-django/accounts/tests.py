from django.test import TestCase
from django.urls import reverse

from .models import Firm, User

GOOD_PASSWORD = "Sturdy-pass-2026"


class SignupTests(TestCase):
    def signup(self, **overrides):
        data = {
            "firm_name": "Nair Associates",
            "email": "owner@nair.example",
            "password1": GOOD_PASSWORD,
            "password2": GOOD_PASSWORD,
        }
        data.update(overrides)
        return self.client.post(reverse("signup"), data)

    def test_signup_creates_firm_and_admin(self):
        response = self.signup()
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(email="owner@nair.example")
        self.assertEqual(user.firm.name, "Nair Associates")
        self.assertEqual(user.role, User.ROLE_ADMIN)
        self.assertEqual(Firm.objects.count(), 1)

    def test_duplicate_email_is_rejected_and_creates_no_firm(self):
        self.signup()
        self.client.logout()
        self.signup(firm_name="Other Firm")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Firm.objects.count(), 1)

    def test_password_mismatch_is_rejected(self):
        self.signup(password2="different-password-1")
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Firm.objects.count(), 0)


class AccessTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_login_and_dashboard_show_firm(self):
        firm = Firm.objects.create(name="Menon Studio")
        User.objects.create_user(
            email="a@menon.example", password=GOOD_PASSWORD, firm=firm, role=User.ROLE_ADMIN
        )
        self.assertTrue(self.client.login(username="a@menon.example", password=GOOD_PASSWORD))
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Menon Studio")

    def test_logout_requires_post_and_logs_out(self):
        firm = Firm.objects.create(name="Menon Studio")
        User.objects.create_user(email="a@menon.example", password=GOOD_PASSWORD, firm=firm)
        self.client.login(username="a@menon.example", password=GOOD_PASSWORD)
        self.client.post(reverse("logout"))
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
