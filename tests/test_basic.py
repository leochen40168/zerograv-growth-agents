import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
TEST_TMP_DIR = ROOT / ".test_tmp"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import email_sender
import vendor_outreach
from email_sender import EmailSenderError, send_vendor_email
from vendor_outreach import VendorOutreachError, add_vendor, generate_vendor_email, load_vendors
from website_content_exporter import export_draft, export_drafts_for_topic, load_draft


@contextmanager
def temporary_directory():
    TEST_TMP_DIR.mkdir(exist_ok=True)
    path = TEST_TMP_DIR / str(uuid.uuid4())
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


@contextmanager
def isolated_outreach_files():
    with temporary_directory() as tmpdir:
        root = Path(tmpdir)
        original_vendors_path = vendor_outreach.VENDORS_PATH
        original_log_path = email_sender.EMAIL_OUTREACH_LOG_PATH
        vendor_outreach.VENDORS_PATH = root / "vendors.csv"
        email_sender.EMAIL_OUTREACH_LOG_PATH = root / "email_outreach_log.csv"
        try:
            yield root
        finally:
            vendor_outreach.VENDORS_PATH = original_vendors_path
            email_sender.EMAIL_OUTREACH_LOG_PATH = original_log_path


class ProjectStructureTest(unittest.TestCase):
    def test_required_project_files_exist(self):
        root = Path(__file__).resolve().parent.parent
        required_paths = [
            root / "README.md",
            root / "requirements.txt",
            root / ".env.example",
            root / "src" / "app.py",
            root / "src" / "article_generator.py",
            root / "src" / "task_manager.py",
            root / "src" / "lead_tracker.py",
            root / "src" / "content_draft_generator.py",
            root / "src" / "wordpress_draft_publisher.py",
            root / "src" / "website_content_exporter.py",
            root / "src" / "vendor_outreach.py",
            root / "src" / "email_sender.py",
            root / "src" / "daily_workflow.py",
            root / "src" / "review_queue.py",
            root / "src" / "metrics_tracker.py",
            root / "data" / "topics.csv",
            root / "data" / "posting_tasks.csv",
            root / "data" / "seller_leads.csv",
            root / "data" / "vendors.csv",
            root / "data" / "email_outreach_log.csv",
            root / "data" / "content_reviews.csv",
            root / "data" / "metrics.csv",
            root / "prompts" / "seo_article_prompt.md",
        ]
        for path in required_paths:
            self.assertTrue(path.exists(), f"Missing required path: {path}")

    def test_tests_can_use_temporary_directory(self):
        with temporary_directory() as tmpdir:
            temp_path = Path(tmpdir) / "sample.txt"
            temp_path.write_text("ok", encoding="utf-8")
            self.assertEqual(temp_path.read_text(encoding="utf-8"), "ok")


class WebsiteContentExporterTest(unittest.TestCase):
    def test_load_draft_markdown(self):
        with temporary_directory() as tmpdir:
            draft_path = Path(tmpdir) / "draft-topic-1-seo-article.md"
            draft_path.write_text("# Draft\n\nBody", encoding="utf-8")

            self.assertEqual(load_draft(str(draft_path)), "# Draft\n\nBody")

    def test_export_single_draft_with_metadata(self):
        with temporary_directory() as tmpdir:
            root = Path(tmpdir)
            draft_path = root / "draft-topic-1-facebook-page-post.md"
            output_dir = root / "exports"
            draft_path.write_text("Post body", encoding="utf-8")

            exported_path = Path(export_draft(str(draft_path), output_dir=str(output_dir)))
            exported_text = exported_path.read_text(encoding="utf-8")

            self.assertTrue(exported_path.exists())
            self.assertEqual(exported_path.name, "export-draft-topic-1-facebook-page-post.md")
            self.assertIn(f"source_draft: {draft_path}", exported_text)
            self.assertIn("export_type: facebook_page_post", exported_text)
            self.assertIn("publish_method: manual_copy", exported_text)
            self.assertIn("Post body", exported_text)

    def test_export_multiple_drafts_for_topic_id(self):
        with temporary_directory() as tmpdir:
            root = Path(tmpdir)
            drafts_dir = root / "drafts"
            output_dir = root / "exports"
            drafts_dir.mkdir()
            (drafts_dir / "draft-topic-2-seo-article.md").write_text("Article", encoding="utf-8")
            (drafts_dir / "draft-topic-2-facebook-group-post.md").write_text("Group", encoding="utf-8")
            (drafts_dir / "draft-topic-3-seo-article.md").write_text("Other", encoding="utf-8")

            exported_paths = export_drafts_for_topic(
                2,
                drafts_dir=str(drafts_dir),
                output_dir=str(output_dir),
            )

            self.assertEqual(len(exported_paths), 2)
            self.assertEqual(
                sorted(Path(path).name for path in exported_paths),
                [
                    "export-draft-topic-2-facebook-group-post.md",
                    "export-draft-topic-2-seo-article.md",
                ],
            )

    def test_export_does_not_call_facebook_or_wordpress_api(self):
        with temporary_directory() as tmpdir:
            root = Path(tmpdir)
            draft_path = root / "draft-topic-1-seo-article.md"
            output_dir = root / "exports"
            draft_path.write_text("Article body", encoding="utf-8")

            with patch("urllib.request.urlopen") as urlopen:
                exported_path = export_draft(str(draft_path), output_dir=str(output_dir))

            urlopen.assert_not_called()
            exported_text = Path(exported_path).read_text(encoding="utf-8")
            self.assertIn("export_type: website_article", exported_text)


class VendorEmailOutreachTest(unittest.TestCase):
    def test_add_vendor_and_auto_increment_id(self):
        with isolated_outreach_files():
            first_id = add_vendor(
                "Alpha Instruments",
                email="sales@example.com",
                source_url="https://example.com/contact",
                source_type="website",
            )
            second_id = add_vendor(
                "Beta Instruments",
                email="info@example.com",
                source_url="https://example.com/vendors",
                source_type="manual",
            )

            vendors = load_vendors()
            self.assertEqual(first_id, 1)
            self.assertEqual(second_id, 2)
            self.assertEqual(len(vendors), 2)

    def test_invalid_contact_status_raises(self):
        with isolated_outreach_files():
            with self.assertRaises(VendorOutreachError):
                add_vendor("Alpha Instruments", contact_status="bad_status")

    def test_generate_vendor_email_initial(self):
        with isolated_outreach_files():
            vendor_id = add_vendor(
                "Alpha Instruments",
                category="二手量測儀器",
                email="sales@example.com",
                source_url="https://example.com/contact",
            )

            email = generate_vendor_email(vendor_id, template_type="initial")

            self.assertIn("ZeroGrav", email["subject"])
            self.assertIn("免費", email["body"])
            self.assertIn("3-5", email["body"])
            self.assertIn("不需聯繫", email["body"])

    def test_generate_vendor_email_follow_up(self):
        with isolated_outreach_files():
            vendor_id = add_vendor(
                "Alpha Instruments",
                email="sales@example.com",
                source_url="https://example.com/contact",
            )

            email = generate_vendor_email(vendor_id, template_type="follow_up")

            self.assertIn("追蹤", email["subject"])
            self.assertIn("不承諾成交", email["body"])
            self.assertIn("不需聯繫", email["body"])

    def test_send_disabled_cannot_send(self):
        with isolated_outreach_files():
            vendor_id = add_vendor(
                "Alpha Instruments",
                email="sales@example.com",
                source_url="https://example.com/contact",
            )
            with patch.dict("os.environ", {"EMAIL_SEND_ENABLED": "false"}, clear=True):
                with patch("email_sender.smtplib.SMTP") as smtp:
                    with self.assertRaises(EmailSenderError):
                        send_vendor_email(vendor_id)

            smtp.assert_not_called()

    def test_blank_email_cannot_send(self):
        with isolated_outreach_files():
            vendor_id = add_vendor("Alpha Instruments", source_url="https://example.com/contact")
            with self.assertRaises(EmailSenderError):
                send_vendor_email(vendor_id)

    def test_blank_source_url_cannot_send(self):
        with isolated_outreach_files():
            vendor_id = add_vendor("Alpha Instruments", email="sales@example.com")
            with self.assertRaises(EmailSenderError):
                send_vendor_email(vendor_id)

    def test_opted_out_and_not_interested_cannot_send(self):
        with isolated_outreach_files():
            opted_out_id = add_vendor(
                "Alpha Instruments",
                email="sales@example.com",
                source_url="https://example.com/contact",
                contact_status="opted_out",
            )
            not_interested_id = add_vendor(
                "Beta Instruments",
                email="info@example.com",
                source_url="https://example.com/contact",
                contact_status="not_interested",
            )

            with self.assertRaises(EmailSenderError):
                send_vendor_email(opted_out_id)
            with self.assertRaises(EmailSenderError):
                send_vendor_email(not_interested_id)

    def test_email_sent_cannot_send_again_without_status_change(self):
        with isolated_outreach_files():
            vendor_id = add_vendor(
                "Alpha Instruments",
                email="sales@example.com",
                source_url="https://example.com/contact",
                contact_status="email_sent",
            )

            with self.assertRaises(EmailSenderError):
                send_vendor_email(vendor_id)

    def test_mock_smtp_success_writes_log(self):
        with isolated_outreach_files():
            vendor_id = add_vendor(
                "Alpha Instruments",
                email="sales@example.com",
                source_url="https://example.com/contact",
            )
            env = {
                "EMAIL_SEND_ENABLED": "true",
                "EMAIL_SMTP_HOST": "smtp.example.com",
                "EMAIL_SMTP_PORT": "587",
                "EMAIL_SMTP_USERNAME": "user",
                "EMAIL_SMTP_PASSWORD": "password",
                "EMAIL_FROM_NAME": "ZeroGrav",
                "EMAIL_FROM_ADDRESS": "hello@zerograv.com.tw",
                "EMAIL_DAILY_LIMIT": "20",
            }
            with patch.dict("os.environ", env, clear=True):
                with patch("email_sender.smtplib.SMTP") as smtp:
                    result = send_vendor_email(vendor_id)

            self.assertEqual(result["status"], "sent")
            smtp.return_value.__enter__.return_value.send_message.assert_called_once()
            log = email_sender.load_email_log()
            self.assertEqual(len(log), 1)
            self.assertEqual(log.iloc[0]["status"], "sent")
            vendor = vendor_outreach.get_vendor(vendor_id)
            self.assertEqual(vendor["contact_status"], "email_sent")

    def test_daily_limit_blocks_sending(self):
        with isolated_outreach_files():
            vendor_id = add_vendor(
                "Alpha Instruments",
                email="sales@example.com",
                source_url="https://example.com/contact",
            )
            email_sender.append_email_log(
                vendor_id,
                "sent@example.com",
                "initial",
                "Already sent",
                "sent",
            )
            env = {
                "EMAIL_SEND_ENABLED": "true",
                "EMAIL_SMTP_HOST": "smtp.example.com",
                "EMAIL_SMTP_PORT": "587",
                "EMAIL_SMTP_USERNAME": "user",
                "EMAIL_SMTP_PASSWORD": "password",
                "EMAIL_FROM_NAME": "ZeroGrav",
                "EMAIL_FROM_ADDRESS": "hello@zerograv.com.tw",
                "EMAIL_DAILY_LIMIT": "1",
            }
            with patch.dict("os.environ", env, clear=True):
                with patch("email_sender.smtplib.SMTP") as smtp:
                    with self.assertRaises(EmailSenderError):
                        send_vendor_email(vendor_id)

            smtp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
