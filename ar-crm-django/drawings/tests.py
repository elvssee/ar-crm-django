import shutil
import tempfile

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Firm, User
from clients.models import Client
from projects.models import Project

from .models import Drawing, DrawingFile

PASSWORD = "Sturdy-pass-2026"


class DrawingTestCase(TestCase):
    """Base class: uploads go to a throw-away folder, and two firms exist."""

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
        self.nair = Client.objects.create(firm=self.firm, name="Mr Nair")
        self.project = Project.objects.create(firm=self.firm, client=self.nair, title="Site 1")

        self.other_firm = Firm.objects.create(name="Beta Studio")
        self.other_admin = User.objects.create_user(
            email="boss@beta.example", password=PASSWORD, firm=self.other_firm, role=User.ROLE_ADMIN
        )

    def login(self, email):
        self.assertTrue(self.client.login(username=email, password=PASSWORD))

    def upload(self, files=None, **overrides):
        if files is None:
            files = [
                SimpleUploadedFile("plan.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
                SimpleUploadedFile("plan.dwg", b"DWGDATA"),
            ]
        data = {"title": "Ground floor plan", "revision": "Rev A", "note": "For review", "files": files}
        data.update(overrides)
        return self.client.post(reverse("drawing_upload", args=[self.project.pk]), data)

    def make_drawing(self, uploaded_by=None, title="Section A"):
        drawing = Drawing.objects.create(
            firm=self.firm, project=self.project, title=title, uploaded_by=uploaded_by
        )
        DrawingFile.objects.create(
            firm=self.firm, drawing=drawing, original_name="a.pdf", size=5,
            file=SimpleUploadedFile("a.pdf", b"%PDF-1.4"),
        )
        return drawing


class UploadTests(DrawingTestCase):
    def test_login_required(self):
        response = self.client.get(reverse("drawing_feed"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_junior_can_upload_several_files(self):
        self.login("junior@alpha.example")
        response = self.upload()
        self.assertRedirects(response, reverse("project_drawings", args=[self.project.pk]))
        drawing = Drawing.objects.get()
        self.assertEqual(drawing.firm, self.firm)
        self.assertEqual(drawing.project, self.project)
        self.assertEqual(drawing.uploaded_by, self.junior)
        self.assertEqual(drawing.revision, "Rev A")
        self.assertEqual(drawing.files.count(), 2)
        self.assertEqual({f.original_name for f in drawing.files.all()}, {"plan.pdf", "plan.dwg"})

    def test_autocad_and_sketchup_files_are_accepted(self):
        self.login("junior@alpha.example")
        self.upload(files=[
            SimpleUploadedFile("house.skp", b"SKPDATA"),
            SimpleUploadedFile("house.dxf", b"DXFDATA"),
        ])
        self.assertEqual(DrawingFile.objects.count(), 2)

    def test_disallowed_file_type_is_rejected(self):
        self.login("junior@alpha.example")
        self.upload(files=[SimpleUploadedFile("virus.exe", b"MZ")])
        self.assertEqual(Drawing.objects.count(), 0)
        self.assertEqual(DrawingFile.objects.count(), 0)

    @override_settings(DRAWING_MAX_UPLOAD_MB=1)
    def test_oversized_file_is_rejected(self):
        self.login("junior@alpha.example")
        self.upload(files=[SimpleUploadedFile("big.pdf", b"x" * (2 * 1024 * 1024))])
        self.assertEqual(Drawing.objects.count(), 0)

    def test_title_and_file_are_required(self):
        self.login("junior@alpha.example")
        self.client.post(reverse("drawing_upload", args=[self.project.pk]), {"title": ""})
        self.assertEqual(Drawing.objects.count(), 0)

    def test_firm_in_form_data_is_ignored(self):
        self.login("junior@alpha.example")
        self.upload(firm=self.other_firm.pk)
        self.assertEqual(Drawing.objects.get().firm, self.firm)


class DownloadTests(DrawingTestCase):
    def setUp(self):
        super().setUp()
        self.login("junior@alpha.example")
        self.upload()
        self.pdf = DrawingFile.objects.get(original_name="plan.pdf")
        self.dwg = DrawingFile.objects.get(original_name="plan.dwg")

    def test_pdf_opens_inline_and_content_is_correct(self):
        response = self.client.get(reverse("drawing_file", args=[self.pdf.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4 test")
        self.assertTrue(response["Content-Disposition"].startswith("inline"))
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_dwg_is_downloaded_as_attachment(self):
        response = self.client.get(reverse("drawing_file", args=[self.dwg.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))
        self.assertIn("plan.dwg", response["Content-Disposition"])

    def test_anonymous_cannot_download(self):
        self.client.logout()
        response = self.client.get(reverse("drawing_file", args=[self.pdf.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_other_firm_cannot_download(self):
        self.client.logout()
        self.login("boss@beta.example")
        self.assertEqual(self.client.get(reverse("drawing_file", args=[self.pdf.pk])).status_code, 404)

    def test_uploaded_files_are_not_reachable_by_direct_path(self):
        # There is no public /media/ route: files only come out through the permission-checked view.
        response = self.client.get("/media/" + self.pdf.file.name)
        self.assertEqual(response.status_code, 404)


class NewBadgeTests(DrawingTestCase):
    def test_admin_sees_new_for_junior_upload_until_opening_project(self):
        self.make_drawing(uploaded_by=self.junior)
        self.login("boss@alpha.example")
        self.assertContains(self.client.get(reverse("drawing_feed")), "data-new-badge")
        self.assertContains(self.client.get(reverse("project_drawings", args=[self.project.pk])), "data-new-badge")
        self.assertNotContains(self.client.get(reverse("drawing_feed")), "data-new-badge")

    def test_uploader_does_not_see_own_upload_as_new(self):
        self.make_drawing(uploaded_by=self.junior)
        self.login("junior@alpha.example")
        self.assertNotContains(self.client.get(reverse("drawing_feed")), "data-new-badge")


class PermissionTests(DrawingTestCase):
    def test_junior_cannot_delete_or_edit_someone_elses_drawing(self):
        drawing = self.make_drawing(uploaded_by=self.admin)
        self.login("junior@alpha.example")
        self.assertEqual(self.client.post(reverse("drawing_delete", args=[drawing.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("drawing_edit", args=[drawing.pk])).status_code, 403)
        self.assertTrue(Drawing.objects.filter(pk=drawing.pk).exists())

    def test_junior_can_edit_and_delete_own_drawing_and_file_is_removed(self):
        drawing = self.make_drawing(uploaded_by=self.junior)
        stored_name = drawing.files.get().file.name
        self.assertTrue(default_storage.exists(stored_name))
        self.login("junior@alpha.example")
        self.client.post(
            reverse("drawing_edit", args=[drawing.pk]),
            {"title": "Section A revised", "revision": "Rev C", "note": ""},
        )
        drawing.refresh_from_db()
        self.assertEqual(drawing.revision, "Rev C")
        self.client.post(reverse("drawing_delete", args=[drawing.pk]))
        self.assertFalse(Drawing.objects.filter(pk=drawing.pk).exists())
        self.assertFalse(default_storage.exists(stored_name))

    def test_admin_can_delete_any_drawing_in_firm(self):
        drawing = self.make_drawing(uploaded_by=self.junior)
        self.login("boss@alpha.example")
        self.client.post(reverse("drawing_delete", args=[drawing.pk]))
        self.assertFalse(Drawing.objects.filter(pk=drawing.pk).exists())

    def test_project_with_drawings_cannot_be_deleted(self):
        self.make_drawing(uploaded_by=self.junior)
        self.login("boss@alpha.example")
        response = self.client.post(reverse("project_delete", args=[self.project.pk]), follow=True)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())
        self.assertContains(response, "still has drawings")


class TenantIsolationTests(DrawingTestCase):
    def setUp(self):
        super().setUp()
        self.drawing = self.make_drawing(uploaded_by=self.junior, title="Alpha Secret Drawing")
        self.login("boss@beta.example")

    def test_other_firm_cannot_see_drawings(self):
        self.assertNotContains(self.client.get(reverse("drawing_feed")), "Alpha Secret Drawing")
        self.assertEqual(self.client.get(reverse("project_drawings", args=[self.project.pk])).status_code, 404)

    def test_other_firm_cannot_upload_to_this_project(self):
        response = self.client.post(
            reverse("drawing_upload", args=[self.project.pk]),
            {"title": "Sneaky", "files": [SimpleUploadedFile("x.pdf", b"%PDF")]},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Drawing.objects.filter(title="Sneaky").exists())

    def test_other_firm_cannot_edit_or_delete(self):
        self.assertEqual(self.client.get(reverse("drawing_edit", args=[self.drawing.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("drawing_delete", args=[self.drawing.pk])).status_code, 404)
        self.assertTrue(Drawing.objects.filter(pk=self.drawing.pk).exists())
