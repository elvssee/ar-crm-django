from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from .models import ChatSeen, Message
from .test_panel import AJAX, PanelTestCase


class SendTests(PanelTestCase):
    def test_login_required(self):
        response = self.client.post(reverse("general_send"), {"body": "hi"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.assertEqual(Message.objects.count(), 0)

    def test_junior_can_post_and_everyone_in_firm_sees_it(self):
        self.login("junior@alpha.example")
        self.client.post(reverse("general_send"), {"body": "Drawings are ready"}, headers=AJAX)
        self.client.logout()
        self.login("boss@alpha.example")
        self.assertContains(self.client.get(reverse("panel_general")), "Drawings are ready")

    def test_empty_and_too_long_messages_are_rejected(self):
        self.login("junior@alpha.example")
        self.client.post(reverse("general_send"), {"body": "   "}, headers=AJAX)
        self.client.post(reverse("general_send"), {"body": "x" * 2001}, headers=AJAX)
        self.assertEqual(Message.objects.count(), 0)

    def test_ajax_send_returns_the_message_fragment(self):
        self.login("junior@alpha.example")
        response = self.client.post(reverse("general_send"), {"body": "Hello"}, headers=AJAX)
        self.assertEqual(response.status_code, 201)
        self.assertContains(response, "Hello", status_code=201)
        self.assertContains(response, "data-message-id", status_code=201)

    def test_message_text_is_escaped(self):
        self.login("junior@alpha.example")
        self.client.post(reverse("general_send"), {"body": "<script>alert(1)</script>"}, headers=AJAX)
        response = self.client.get(reverse("panel_general"))
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_non_ajax_send_goes_back_to_the_dashboard(self):
        self.login("junior@alpha.example")
        response = self.client.post(reverse("general_send"), {"body": "hello"})
        self.assertRedirects(response, reverse("dashboard"))


class PollTests(PanelTestCase):
    def test_poll_returns_only_newer_messages(self):
        first = self.say(self.admin, "First message")
        self.say(self.admin, "Second message")
        self.login("junior@alpha.example")
        response = self.client.get(reverse("general_poll"), {"after": first.pk}, headers=AJAX)
        self.assertContains(response, "Second message")
        self.assertNotContains(response, "First message")

    def test_poll_with_nothing_new_is_empty(self):
        last = self.say(self.admin, "Only message")
        self.login("junior@alpha.example")
        response = self.client.get(reverse("general_poll"), {"after": last.pk}, headers=AJAX)
        self.assertEqual(response.content, b"")

    def test_poll_ignores_garbage_after_value(self):
        self.say(self.admin, "Hello")
        self.login("junior@alpha.example")
        response = self.client.get(reverse("general_poll"), {"after": "abc"}, headers=AJAX)
        self.assertContains(response, "Hello")


class UnreadTests(PanelTestCase):
    def test_unread_count_clears_when_the_chat_is_opened(self):
        self.say(self.junior, "Drawing is ready")
        self.login("boss@alpha.example")
        self.assertEqual(self.client.get(reverse("dashboard")).context["unread_total"], 1)
        self.assertContains(self.client.get(reverse("panel_general")), "data-new-badge")
        self.assertEqual(self.client.get(reverse("discussion_unread")).json(), {"total": 0})

    def test_own_messages_are_never_unread(self):
        self.say(self.junior, "My own message")
        self.login("junior@alpha.example")
        self.assertEqual(self.client.get(reverse("discussion_unread")).json(), {"total": 0})

    def test_new_message_after_reading_counts_again(self):
        first = self.say(self.junior, "First")
        self.login("boss@alpha.example")
        self.client.get(reverse("panel_general"))
        # Fixed times, so the result never depends on the clock's resolution (Windows is coarse):
        # First was sent 2 minutes ago, it was read 1 minute ago, and Second arrives now.
        now = timezone.now()
        Message.objects.filter(pk=first.pk).update(created_at=now - timedelta(minutes=2))
        ChatSeen.objects.filter(user__email="boss@alpha.example").update(last_seen=now - timedelta(minutes=1))
        self.say(self.junior, "Second")
        self.assertEqual(self.client.get(reverse("discussion_unread")).json(), {"total": 1})

    def test_old_project_messages_are_not_counted(self):
        self.say(self.junior, "Old project thread message", project=self.site1)
        self.login("boss@alpha.example")
        self.assertEqual(self.client.get(reverse("discussion_unread")).json(), {"total": 0})


class DeleteTests(PanelTestCase):
    def test_author_can_delete_own_message(self):
        message = self.say(self.junior, "Oops")
        self.login("junior@alpha.example")
        self.client.post(reverse("discussion_delete", args=[message.pk]))
        self.assertFalse(Message.objects.filter(pk=message.pk).exists())

    def test_junior_cannot_delete_someone_elses_message(self):
        message = self.say(self.admin, "Boss message")
        self.login("junior@alpha.example")
        response = self.client.post(reverse("discussion_delete", args=[message.pk]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Message.objects.filter(pk=message.pk).exists())

    def test_admin_can_delete_any_message_in_firm(self):
        message = self.say(self.junior, "Off topic")
        self.login("boss@alpha.example")
        self.client.post(reverse("discussion_delete", args=[message.pk]))
        self.assertFalse(Message.objects.filter(pk=message.pk).exists())

    def test_delete_requires_post(self):
        message = self.say(self.junior, "Keep me")
        self.login("junior@alpha.example")
        self.assertEqual(self.client.get(reverse("discussion_delete", args=[message.pk])).status_code, 405)
