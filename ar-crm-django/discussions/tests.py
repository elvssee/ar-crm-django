import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Firm, User
from clients.models import Client
from drawings.models import Drawing
from projects.models import Project

from .models import Message

PASSWORD = "Sturdy-pass-2026"
AJAX = {"x-requested-with": "XMLHttpRequest"}


class DiscussionTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp()
        cls._override = override_settings(MEDIA_ROOT=cls._media)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)

    def setUp(self):
        self.firm = Firm.objects.create(name="Alpha Architects")
        self.admin = User.objects.create_user(
            email="boss@alpha.example", password=PASSWORD, firm=self.firm, role=User.ROLE_ADMIN
        )
        self.junior = User.objects.create_user(
            email="junior@alpha.example", password=PASSWORD, firm=self.firm, role=User.ROLE_MEMBER
        )
        nair = Client.objects.create(firm=self.firm, name="Mr Nair")
        self.project = Project.objects.create(firm=self.firm, client=nair, title="Site 1")
        self.other_project = Project.objects.create(firm=self.firm, client=nair, title="Site 2")

        self.other_firm = Firm.objects.create(name="Beta Studio")
        self.other_admin = User.objects.create_user(
            email="boss@beta.example", password=PASSWORD, firm=self.other_firm, role=User.ROLE_ADMIN
        )

        self.thread_url = reverse("project_discussion", args=[self.project.pk])
        self.send_url = reverse("discussion_send", args=[self.project.pk])
        self.poll_url = reverse("discussion_poll", args=[self.project.pk])

    def login(self, email):
        self.assertTrue(self.client.login(username=email, password=PASSWORD))

    def say(self, author, body, project=None):
        return Message.objects.create(
            firm=self.firm, project=project or self.project, author=author, body=body
        )


class SendTests(DiscussionTestCase):
    def test_login_required(self):
        response = self.client.get(self.thread_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_junior_can_post_and_everyone_in_firm_sees_it(self):
        self.login("junior@alpha.example")
        response = self.client.post(self.send_url, {"body": "Plan uploaded, please check stairs"})
        self.assertRedirects(response, self.thread_url)
        message = Message.objects.get()
        self.assertEqual(message.firm, self.firm)
        self.assertEqual(message.project, self.project)
        self.assertEqual(message.author, self.junior)
        self.client.logout()
        self.login("boss@alpha.example")
        self.assertContains(self.client.get(self.thread_url), "Plan uploaded, please check stairs")

    def test_empty_and_too_long_messages_are_rejected(self):
        self.login("junior@alpha.example")
        self.client.post(self.send_url, {"body": "   "})
        self.client.post(self.send_url, {"body": "x" * 2001})
        self.assertEqual(Message.objects.count(), 0)

    def test_ajax_send_returns_the_message_fragment(self):
        self.login("junior@alpha.example")
        response = self.client.post(self.send_url, {"body": "Quick note"}, headers=AJAX)
        self.assertEqual(response.status_code, 201)
        self.assertContains(response, "Quick note", status_code=201)
        self.assertContains(response, "data-message-id", status_code=201)

    def test_ajax_send_with_empty_body_is_400(self):
        self.login("junior@alpha.example")
        response = self.client.post(self.send_url, {"body": ""}, headers=AJAX)
        self.assertEqual(response.status_code, 400)

    def test_message_text_is_escaped(self):
        self.login("junior@alpha.example")
        self.client.post(self.send_url, {"body": "<script>alert(1)</script>"})
        response = self.client.get(self.thread_url)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_can_attach_a_drawing_of_the_same_project(self):
        drawing = Drawing.objects.create(firm=self.firm, project=self.project, title="Ground floor", revision="Rev B")
        self.login("junior@alpha.example")
        self.client.post(self.send_url, {"body": "See this", "drawing": drawing.pk})
        self.assertEqual(Message.objects.get().drawing, drawing)
        self.assertContains(self.client.get(self.thread_url), "Ground floor")

    def test_cannot_attach_a_drawing_from_another_project_or_firm(self):
        elsewhere = Drawing.objects.create(firm=self.firm, project=self.other_project, title="Other site")
        beta_client = Client.objects.create(firm=self.other_firm, name="Beta client")
        beta_project = Project.objects.create(firm=self.other_firm, client=beta_client, title="Beta site")
        foreign = Drawing.objects.create(firm=self.other_firm, project=beta_project, title="Foreign")
        self.login("junior@alpha.example")
        self.client.post(self.send_url, {"body": "x", "drawing": elsewhere.pk})
        self.client.post(self.send_url, {"body": "y", "drawing": foreign.pk})
        self.assertEqual(Message.objects.count(), 0)


class PollTests(DiscussionTestCase):
    def test_poll_returns_only_newer_messages(self):
        first = self.say(self.admin, "First message")
        self.say(self.admin, "Second message")
        self.login("junior@alpha.example")
        response = self.client.get(self.poll_url, {"after": first.pk}, headers=AJAX)
        self.assertContains(response, "Second message")
        self.assertNotContains(response, "First message")

    def test_poll_with_nothing_new_is_empty(self):
        last = self.say(self.admin, "Only message")
        self.login("junior@alpha.example")
        response = self.client.get(self.poll_url, {"after": last.pk}, headers=AJAX)
        self.assertEqual(response.content, b"")

    def test_poll_ignores_garbage_after_value(self):
        self.say(self.admin, "Hello")
        self.login("junior@alpha.example")
        response = self.client.get(self.poll_url, {"after": "abc"}, headers=AJAX)
        self.assertContains(response, "Hello")

    def test_poll_is_per_project(self):
        self.say(self.admin, "On site two", project=self.other_project)
        self.login("junior@alpha.example")
        response = self.client.get(self.poll_url, {"after": 0}, headers=AJAX)
        self.assertEqual(response.content, b"")


class UnreadTests(DiscussionTestCase):
    def test_unread_count_clears_when_thread_is_opened(self):
        self.say(self.junior, "Drawing is ready")
        self.login("boss@alpha.example")
        inbox = self.client.get(reverse("discussion_inbox"))
        self.assertContains(inbox, "data-unread-badge")
        self.assertEqual(inbox.context["unread_total"], 1)

        self.assertContains(self.client.get(self.thread_url), "data-new-badge")
        inbox = self.client.get(reverse("discussion_inbox"))
        self.assertNotContains(inbox, "data-unread-badge")
        self.assertEqual(inbox.context["unread_total"], 0)

    def test_own_messages_are_never_unread(self):
        self.say(self.junior, "My own message")
        self.login("junior@alpha.example")
        inbox = self.client.get(reverse("discussion_inbox"))
        self.assertEqual(inbox.context["unread_total"], 0)

    def test_new_message_after_reading_counts_again(self):
        self.say(self.junior, "First")
        self.login("boss@alpha.example")
        self.client.get(self.thread_url)
        self.say(self.junior, "Second")
        inbox = self.client.get(reverse("discussion_inbox"))
        self.assertEqual(inbox.context["unread_total"], 1)


class DeleteTests(DiscussionTestCase):
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


class TenantIsolationTests(DiscussionTestCase):
    def setUp(self):
        super().setUp()
        self.secret = self.say(self.junior, "Alpha secret chat")
        self.login("boss@beta.example")

    def test_other_firm_cannot_open_send_or_poll(self):
        self.assertEqual(self.client.get(self.thread_url).status_code, 404)
        self.assertEqual(self.client.post(self.send_url, {"body": "intruder"}).status_code, 404)
        self.assertEqual(self.client.get(self.poll_url, headers=AJAX).status_code, 404)
        self.assertEqual(Message.objects.count(), 1)

    def test_other_firm_inbox_is_empty(self):
        inbox = self.client.get(reverse("discussion_inbox"))
        self.assertNotContains(inbox, "Alpha secret chat")
        self.assertNotContains(inbox, "Site 1")

    def test_other_firm_cannot_delete_message(self):
        response = self.client.post(reverse("discussion_delete", args=[self.secret.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Message.objects.filter(pk=self.secret.pk).exists())
