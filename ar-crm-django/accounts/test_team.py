from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Firm, Invitation, User

PASSWORD = "Sturdy-pass-2026"


def make_firm_with_admin(email, firm_name):
    firm = Firm.objects.create(name=firm_name)
    admin = User.objects.create_user(email=email, password=PASSWORD, firm=firm, role=User.ROLE_ADMIN)
    return firm, admin


def add_member(firm, email, role=User.ROLE_MEMBER):
    return User.objects.create_user(email=email, password=PASSWORD, firm=firm, role=role)


class TeamPermissionTests(TestCase):
    def setUp(self):
        self.firm, self.admin = make_firm_with_admin("boss@alpha.example", "Alpha Architects")
        self.junior = add_member(self.firm, "junior@alpha.example")

    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(reverse("team_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_member_cannot_open_team_pages(self):
        self.client.login(username="junior@alpha.example", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("team_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("invite_create")).status_code, 403)

    def test_member_cannot_deactivate_or_change_roles(self):
        self.client.login(username="junior@alpha.example", password=PASSWORD)
        self.assertEqual(self.client.post(reverse("member_set_active", args=[self.admin.pk]), {"active": "0"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("member_set_role", args=[self.admin.pk]), {"role": "member"}).status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(self.admin.role, User.ROLE_ADMIN)

    def test_admin_can_open_team_page(self):
        self.client.login(username="boss@alpha.example", password=PASSWORD)
        response = self.client.get(reverse("team_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "junior@alpha.example")


class InviteTests(TestCase):
    def setUp(self):
        self.firm, self.admin = make_firm_with_admin("boss@alpha.example", "Alpha Architects")
        self.client.login(username="boss@alpha.example", password=PASSWORD)

    def invite(self, email="new@alpha.example", role="member"):
        return self.client.post(reverse("invite_create"), {"email": email, "role": role})

    def test_invite_is_created_for_admins_firm_and_link_is_shown(self):
        response = self.invite()
        self.assertRedirects(response, reverse("team_list"))
        invitation = Invitation.objects.get(email="new@alpha.example")
        self.assertEqual(invitation.firm, self.firm)
        self.assertEqual(invitation.role, "member")
        page = self.client.get(reverse("team_list"))
        self.assertContains(page, reverse("accept_invite", args=[invitation.token]))

    def test_duplicate_pending_invite_is_rejected(self):
        self.invite()
        self.invite()
        self.assertEqual(Invitation.objects.count(), 1)

    def test_email_that_already_has_account_is_rejected(self):
        self.invite(email="boss@alpha.example")
        self.assertEqual(Invitation.objects.count(), 0)

    def test_unknown_role_is_rejected(self):
        self.invite(role="owner")
        self.assertEqual(Invitation.objects.count(), 0)

    def test_revoke_deletes_invitation(self):
        self.invite()
        invitation = Invitation.objects.get()
        self.client.post(reverse("invite_revoke", args=[invitation.pk]))
        self.assertEqual(Invitation.objects.count(), 0)


class AcceptInviteTests(TestCase):
    def setUp(self):
        self.firm, self.admin = make_firm_with_admin("boss@alpha.example", "Alpha Architects")
        self.invitation = Invitation.objects.create(
            firm=self.firm, email="junior@alpha.example", role="member", invited_by=self.admin
        )
        self.url = reverse("accept_invite", args=[self.invitation.token])

    def accept(self, **overrides):
        data = {
            "first_name": "Asha", "last_name": "K",
            "password1": PASSWORD, "password2": PASSWORD,
        }
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_page_shows_firm_name(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Architects")

    def test_accepting_creates_member_in_the_inviting_firm_and_logs_in(self):
        response = self.accept()
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(email="junior@alpha.example")
        self.assertEqual(user.firm, self.firm)
        self.assertEqual(user.role, "member")
        self.assertEqual(user.first_name, "Asha")
        self.invitation.refresh_from_db()
        self.assertIsNotNone(self.invitation.accepted_at)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_link_cannot_be_used_twice(self):
        self.accept()
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 410)
        self.accept(first_name="Intruder")
        self.assertEqual(User.objects.filter(firm=self.firm).count(), 2)

    def test_expired_link_is_rejected(self):
        self.invitation.expires_at = timezone.now() - timedelta(minutes=1)
        self.invitation.save()
        self.assertEqual(self.client.get(self.url).status_code, 410)
        self.accept()
        self.assertFalse(User.objects.filter(email="junior@alpha.example").exists())

    def test_unknown_token_is_404(self):
        self.assertEqual(self.client.get(reverse("accept_invite", args=["nonsense"])).status_code, 404)

    def test_password_mismatch_creates_no_user(self):
        self.accept(password2="different-password-1")
        self.assertFalse(User.objects.filter(email="junior@alpha.example").exists())

    def test_invited_admin_becomes_admin(self):
        self.invitation.role = "admin"
        self.invitation.save()
        self.accept()
        self.assertEqual(User.objects.get(email="junior@alpha.example").role, "admin")


class ManageMembersTests(TestCase):
    def setUp(self):
        self.firm, self.admin = make_firm_with_admin("boss@alpha.example", "Alpha Architects")
        self.junior = add_member(self.firm, "junior@alpha.example")
        self.other_firm, self.other_admin = make_firm_with_admin("boss@beta.example", "Beta Studio")
        self.other_junior = add_member(self.other_firm, "junior@beta.example")
        self.client.login(username="boss@alpha.example", password=PASSWORD)

    def test_deactivated_member_cannot_log_in_and_can_be_reactivated(self):
        self.client.post(reverse("member_set_active", args=[self.junior.pk]), {"active": "0"})
        self.junior.refresh_from_db()
        self.assertFalse(self.junior.is_active)
        other_browser = self.client_class()
        self.assertFalse(other_browser.login(username="junior@alpha.example", password=PASSWORD))

        self.client.post(reverse("member_set_active", args=[self.junior.pk]), {"active": "1"})
        self.junior.refresh_from_db()
        self.assertTrue(self.junior.is_active)
        self.assertTrue(other_browser.login(username="junior@alpha.example", password=PASSWORD))

    def test_admin_cannot_deactivate_self(self):
        self.client.post(reverse("member_set_active", args=[self.admin.pk]), {"active": "0"})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_admin_can_change_role_but_not_own(self):
        self.client.post(reverse("member_set_role", args=[self.junior.pk]), {"role": "admin"})
        self.junior.refresh_from_db()
        self.assertEqual(self.junior.role, "admin")
        self.client.post(reverse("member_set_role", args=[self.admin.pk]), {"role": "member"})
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, "admin")

    def test_unknown_role_is_ignored(self):
        self.client.post(reverse("member_set_role", args=[self.junior.pk]), {"role": "owner"})
        self.junior.refresh_from_db()
        self.assertEqual(self.junior.role, "member")

    def test_admin_cannot_manage_another_firms_people(self):
        self.assertEqual(
            self.client.post(reverse("member_set_active", args=[self.other_junior.pk]), {"active": "0"}).status_code, 404
        )
        self.assertEqual(
            self.client.post(reverse("member_set_role", args=[self.other_junior.pk]), {"role": "admin"}).status_code, 404
        )
        self.other_junior.refresh_from_db()
        self.assertTrue(self.other_junior.is_active)
        self.assertEqual(self.other_junior.role, "member")

    def test_admin_cannot_revoke_another_firms_invitation(self):
        invitation = Invitation.objects.create(firm=self.other_firm, email="x@beta.example")
        self.assertEqual(self.client.post(reverse("invite_revoke", args=[invitation.pk])).status_code, 404)
        self.assertTrue(Invitation.objects.filter(pk=invitation.pk).exists())

    def test_team_page_only_lists_own_firm(self):
        response = self.client.get(reverse("team_list"))
        self.assertContains(response, "junior@alpha.example")
        self.assertNotContains(response, "junior@beta.example")


class PasswordChangeTests(TestCase):
    def test_user_can_change_own_password(self):
        firm, admin = make_firm_with_admin("boss@alpha.example", "Alpha Architects")
        self.client.login(username="boss@alpha.example", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("password_change")).status_code, 200)
        response = self.client.post(
            reverse("password_change"),
            {"old_password": PASSWORD, "new_password1": "Another-pass-2027", "new_password2": "Another-pass-2027"},
        )
        self.assertRedirects(response, reverse("dashboard"))
        admin.refresh_from_db()
        self.assertTrue(admin.check_password("Another-pass-2027"))
