import shutil
import tempfile

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from .models import Message
from .test_panel import AJAX, PanelTestCase


class AttachmentTestCase(PanelTestCase):
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

    def send_file(self, name="plan.pdf", body="", content=b"%PDF-1.4 test"):
        upload = SimpleUploadedFile(name, content)
        return self.client.post(reverse("general_send"), {"body": body, "attachment": upload}, headers=AJAX)


class SendingFilesTests(AttachmentTestCase):
    def test_team_chat_message_can_carry_a_file_and_text(self):
        self.login("junior@alpha.example")
        response = self.send_file(body="Here is the plan")
        self.assertEqual(response.status_code, 201)
        message = Message.objects.get()
        self.assertEqual(message.body, "Here is the plan")
        self.assertEqual(message.attachment_name, "plan.pdf")
        self.assertEqual(message.attachment_size, len(b"%PDF-1.4 test"))
        self.assertContains(response, "plan.pdf", status_code=201)

    def test_file_alone_is_enough(self):
        self.login("junior@alpha.example")
        self.assertEqual(self.send_file().status_code, 201)
        self.assertEqual(Message.objects.get().body, "")

    def test_disallowed_file_type_is_rejected(self):
        self.login("junior@alpha.example")
        response = self.send_file(name="virus.exe")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Message.objects.count(), 0)

    @override_settings(DRAWING_MAX_UPLOAD_MB=0)
    def test_too_large_file_is_rejected(self):
        self.login("junior@alpha.example")
        response = self.send_file()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Message.objects.count(), 0)

    def test_nothing_at_all_is_rejected(self):
        self.login("junior@alpha.example")
        response = self.client.post(reverse("general_send"), {"body": " "}, headers=AJAX)
        self.assertEqual(response.status_code, 400)


class DownloadingFilesTests(AttachmentTestCase):
    def make_message(self, name="plan.pdf"):
        self.login("junior@alpha.example")
        self.send_file(name=name)
        self.client.logout()
        return Message.objects.get()

    def test_same_firm_can_open_a_pdf_inline(self):
        message = self.make_message()
        self.login("boss@alpha.example")
        response = self.client.get(reverse("discussion_file", args=[message.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertNotIn("attachment", response["Content-Disposition"])

    def test_other_file_types_download(self):
        message = self.make_message(name="site.dwg")
        self.login("boss@alpha.example")
        response = self.client.get(reverse("discussion_file", args=[message.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])

    def test_other_firm_gets_404(self):
        message = self.make_message()
        self.login("boss@beta.example")
        self.assertEqual(self.client.get(reverse("discussion_file", args=[message.pk])).status_code, 404)

    def test_login_is_required(self):
        message = self.make_message()
        response = self.client.get(reverse("discussion_file", args=[message.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_message_without_a_file_is_404(self):
        message = self.say(self.junior, "Just text")
        self.login("boss@alpha.example")
        self.assertEqual(self.client.get(reverse("discussion_file", args=[message.pk])).status_code, 404)

    def test_deleting_the_message_deletes_the_file(self):
        message = self.make_message()
        path = message.attachment.name
        self.assertTrue(default_storage.exists(path))
        self.login("junior@alpha.example")
        self.client.post(reverse("discussion_delete", args=[message.pk]), headers=AJAX)
        self.assertFalse(default_storage.exists(path))
        self.assertFalse(Message.objects.filter(pk=message.pk).exists())


class PanelOpensIntoTeamChatTests(AttachmentTestCase):
    def test_panel_is_wired_to_open_the_team_chat_directly(self):
        self.login("boss@alpha.example")
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, 'data-general-url="%s"' % reverse("panel_general"))

    def test_panel_thread_has_file_picker_and_no_back_to_project_list(self):
        self.login("boss@alpha.example")
        response = self.client.get(reverse("panel_general"))
        self.assertContains(response, "data-attach-input")
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertNotContains(response, "data-panel-back")
